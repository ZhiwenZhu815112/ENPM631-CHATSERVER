#!/usr/bin/env python3
"""
Custom Kubernetes Autoscaler for Chat Application
Scales based on Redis online user count

Scaling Logic:
- 1-3 users: 1 Pod
- 4-6 users: 2 Pods
- 7-9 users: 3 Pods
- Every 3 users = 1 Pod (max 10 Pods)
"""

import redis
import time
import os
import sys
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class ChatAutoscaler:
    def __init__(self):
        # Load Kubernetes config
        try:
            # Try in-cluster config first (when running in K8s)
            config.load_incluster_config()
            print("✓ Loaded in-cluster Kubernetes config")
        except:
            # Fall back to local kubeconfig (for development)
            config.load_kube_config()
            print("✓ Loaded local Kubernetes config")

        self.apps_v1 = client.AppsV1Api()

        # Configuration from environment variables
        self.namespace = os.getenv("NAMESPACE", "chat-app")
        self.deployment_name = os.getenv("DEPLOYMENT_NAME", "chat-server")
        self.redis_host = os.getenv("REDIS_HOST", "redis-service.chat-app.svc.cluster.local")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)

        # Scaling parameters
        self.min_replicas = int(os.getenv("MIN_REPLICAS", "1"))
        self.max_replicas = int(os.getenv("MAX_REPLICAS", "10"))
        self.users_per_pod = int(os.getenv("USERS_PER_POD", "3"))
        self.check_interval = int(os.getenv("CHECK_INTERVAL", "10"))  # seconds
        self.scale_down_delay = int(os.getenv("SCALE_DOWN_DELAY", "60"))  # seconds

        # State tracking for scale-down delay
        self.last_scale_down_check = {}

        # Connect to Redis
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password if self.redis_password else None,
            decode_responses=True,
            socket_timeout=5
        )

        print(f"✓ Connected to Redis at {self.redis_host}:{self.redis_port}")
        print(f"Configuration:")
        print(f"  - Namespace: {self.namespace}")
        print(f"  - Deployment: {self.deployment_name}")
        print(f"  - Min Replicas: {self.min_replicas}")
        print(f"  - Max Replicas: {self.max_replicas}")
        print(f"  - Users per Pod: {self.users_per_pod}")
        print(f"  - Check Interval: {self.check_interval}s")
        print(f"  - Scale Down Delay: {self.scale_down_delay}s")
        print()

    def get_online_user_count(self):
        """Get the number of online users from Redis"""
        try:
            count = self.redis_client.scard("online_users")
            return count
        except Exception as e:
            print(f"⚠️  Error getting online user count: {e}")
            return 0

    def get_current_replicas(self):
        """Get current number of replicas in the deployment"""
        try:
            deployment = self.apps_v1.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace
            )
            return deployment.spec.replicas
        except ApiException as e:
            print(f"⚠️  Error reading deployment: {e}")
            return None

    def calculate_desired_replicas(self, user_count):
        """
        Calculate desired number of replicas based on user count

        Formula: replicas = ceil(user_count / users_per_pod)
        With min and max bounds
        """
        if user_count == 0:
            return self.min_replicas

        import math
        desired = math.ceil(user_count / self.users_per_pod)

        # Apply min/max bounds
        desired = max(self.min_replicas, min(desired, self.max_replicas))

        return desired

    def scale_deployment(self, desired_replicas):
        """Scale the deployment to desired number of replicas"""
        try:
            # Update the deployment
            self.apps_v1.patch_namespaced_deployment_scale(
                name=self.deployment_name,
                namespace=self.namespace,
                body={"spec": {"replicas": desired_replicas}}
            )
            print(f"✅ Scaled deployment to {desired_replicas} replicas")
            return True
        except ApiException as e:
            print(f"❌ Error scaling deployment: {e}")
            return False

    def should_scale_down(self, current_replicas, desired_replicas):
        """
        Determine if we should scale down
        Adds delay to prevent frequent scale-downs
        """
        if desired_replicas >= current_replicas:
            # Not scaling down
            return False

        # Check if we need to wait before scaling down
        now = time.time()
        key = f"{current_replicas}->{desired_replicas}"

        if key not in self.last_scale_down_check:
            # First time seeing this scale-down request
            self.last_scale_down_check[key] = now
            print(f"⏳ Scale down from {current_replicas} to {desired_replicas} pending...")
            print(f"   Waiting {self.scale_down_delay}s to confirm...")
            return False

        elapsed = now - self.last_scale_down_check[key]
        if elapsed < self.scale_down_delay:
            remaining = self.scale_down_delay - int(elapsed)
            if remaining % 10 == 0:  # Print every 10 seconds
                print(f"   Still waiting... {remaining}s remaining")
            return False

        # Enough time has passed, allow scale down
        del self.last_scale_down_check[key]
        return True

    def run(self):
        """Main autoscaling loop"""
        print("🚀 Chat Autoscaler started")
        print("=" * 60)

        while True:
            try:
                # Get current state
                user_count = self.get_online_user_count()
                current_replicas = self.get_current_replicas()

                if current_replicas is None:
                    print("⚠️  Could not read current replicas, skipping...")
                    time.sleep(self.check_interval)
                    continue

                # Calculate desired state
                desired_replicas = self.calculate_desired_replicas(user_count)

                # Log current state
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Users: {user_count:2d} | Current: {current_replicas} Pods | Desired: {desired_replicas} Pods", end="")

                # Decide if we need to scale
                if current_replicas == desired_replicas:
                    print(" | ✓ No change needed")
                    # Clear any pending scale-down
                    self.last_scale_down_check.clear()
                elif desired_replicas > current_replicas:
                    # Scale up immediately
                    print(f" | ↗️  SCALING UP")
                    self.scale_deployment(desired_replicas)
                    self.last_scale_down_check.clear()
                else:
                    # Scale down with delay
                    if self.should_scale_down(current_replicas, desired_replicas):
                        print(f" | ↘️  SCALING DOWN")
                        self.scale_deployment(desired_replicas)
                    else:
                        print(f" | ⏳ Scale down pending...")

            except KeyboardInterrupt:
                print("\n\n👋 Autoscaler stopped by user")
                sys.exit(0)
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                import traceback
                traceback.print_exc()

            # Wait before next check
            time.sleep(self.check_interval)

if __name__ == "__main__":
    autoscaler = ChatAutoscaler()
    autoscaler.run()
