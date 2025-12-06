#!/usr/bin/env python3
"""
Chat Server Monitoring Dashboard

A Flask-based web dashboard to monitor the chat server pods,
online users, database status, and autoscaler metrics.

Usage:
    python dashboard.py

Access: http://localhost:5000
"""

import os
import json
import time
import threading
from datetime import datetime, timedelta
from collections import defaultdict, deque
import redis
import psycopg2
from flask import Flask, render_template, jsonify
from kubernetes import client, config
from kubernetes.client.rest import ApiException

app = Flask(__name__)

class ChatMonitor:
    def __init__(self):
        # Initialize Kubernetes client
        try:
            # Try in-cluster config first (when running in K8s)
            config.load_incluster_config()
            print("✓ Loaded in-cluster Kubernetes config")
        except:
            try:
                # Fall back to local kubeconfig
                config.load_kube_config()
                print("✓ Loaded local Kubernetes config")
            except:
                print("⚠️  Failed to load Kubernetes config - K8s monitoring disabled")
                
        self.k8s_apps_v1 = client.AppsV1Api() if 'client' in globals() else None
        self.k8s_core_v1 = client.CoreV1Api() if 'client' in globals() else None

        # Configuration
        self.namespace = os.getenv("NAMESPACE", "chat-app")
        self.deployment_name = os.getenv("DEPLOYMENT_NAME", "chat-server")
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # Database configuration
        self.db_host = os.getenv("DB_HOST", "localhost")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "chatdb")
        self.db_user = os.getenv("DB_USER", "chatuser")
        self.db_pass = os.getenv("DB_PASS", "chatpass")

        # Data storage for metrics
        self.metrics_history = {
            'timestamps': deque(maxlen=60),  # Last 60 data points (5 minutes at 5s intervals)
            'user_count': deque(maxlen=60),
            'replica_count': deque(maxlen=60),
            'ready_pods': deque(maxlen=60),
            'cpu_usage': deque(maxlen=60),
            'memory_usage': deque(maxlen=60)
        }
        
        self.current_status = {
            'online_users': 0,
            'total_users': 0,
            'replicas': {'desired': 0, 'ready': 0, 'available': 0},
            'pods': [],
            'database_status': 'unknown',
            'redis_status': 'unknown',
            'autoscaler_status': 'unknown',
            'last_updated': None,
            'uptime': None,
            'total_messages': 0
        }

        # Connect to services
        self.redis_client = None
        self.connect_redis()
        
        # Start monitoring thread
        self.start_time = datetime.now()
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

    def connect_redis(self):
        """Connect to Redis"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password if self.redis_password else None,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.current_status['redis_status'] = 'connected'
            print(f"✓ Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            self.current_status['redis_status'] = f'error: {str(e)}'
            print(f"⚠️  Redis connection failed: {e}")

    def get_database_status(self):
        """Check database connectivity"""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass,
                connect_timeout=5
            )
            cursor = conn.cursor()
            
            # Get user count
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Get message count
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            self.current_status['database_status'] = 'connected'
            self.current_status['total_users'] = total_users
            self.current_status['total_messages'] = total_messages
            
        except Exception as e:
            self.current_status['database_status'] = f'error: {str(e)}'
            print(f"⚠️  Database check failed: {e}")

    def get_redis_metrics(self):
        """Get metrics from Redis"""
        if not self.redis_client:
            return
            
        try:
            # Get online users count
            online_users = self.redis_client.scard("online_users")
            self.current_status['online_users'] = online_users
            
            # Get online users list
            online_users_list = list(self.redis_client.smembers("online_users"))
            self.current_status['online_users_list'] = online_users_list
            
        except Exception as e:
            print(f"⚠️  Redis metrics failed: {e}")
            self.current_status['redis_status'] = f'error: {str(e)}'

    def get_kubernetes_status(self):
        """Get Kubernetes deployment and pod status"""
        if not self.k8s_apps_v1 or not self.k8s_core_v1:
            return
            
        try:
            # Get deployment status
            deployment = self.k8s_apps_v1.read_namespaced_deployment(
                name=self.deployment_name,
                namespace=self.namespace
            )
            
            self.current_status['replicas'] = {
                'desired': deployment.spec.replicas or 0,
                'ready': deployment.status.ready_replicas or 0,
                'available': deployment.status.available_replicas or 0,
                'updated': deployment.status.updated_replicas or 0
            }
            
            # Get pod details
            pods = self.k8s_core_v1.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app={self.deployment_name}"
            )
            
            pod_list = []
            for pod in pods.items:
                pod_info = {
                    'name': pod.metadata.name,
                    'phase': pod.status.phase,
                    'ready': False,
                    'restarts': 0,
                    'age': None,
                    'node': pod.spec.node_name,
                    'ip': pod.status.pod_ip
                }
                
                # Check if pod is ready
                if pod.status.conditions:
                    for condition in pod.status.conditions:
                        if condition.type == 'Ready':
                            pod_info['ready'] = condition.status == 'True'
                            break
                
                # Get restart count
                if pod.status.container_statuses:
                    pod_info['restarts'] = pod.status.container_statuses[0].restart_count
                
                # Calculate age
                if pod.metadata.creation_timestamp:
                    age = datetime.now(pod.metadata.creation_timestamp.tzinfo) - pod.metadata.creation_timestamp
                    pod_info['age'] = str(age).split('.')[0]  # Remove microseconds
                
                pod_list.append(pod_info)
            
            self.current_status['pods'] = pod_list
            
            # Check autoscaler pod
            try:
                autoscaler_pods = self.k8s_core_v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector="app=chat-autoscaler"
                )
                
                if autoscaler_pods.items:
                    autoscaler_pod = autoscaler_pods.items[0]
                    if autoscaler_pod.status.phase == 'Running':
                        self.current_status['autoscaler_status'] = 'running'
                    else:
                        self.current_status['autoscaler_status'] = autoscaler_pod.status.phase
                else:
                    self.current_status['autoscaler_status'] = 'not found'
            except Exception as e:
                self.current_status['autoscaler_status'] = f'error: {str(e)}'
                
        except ApiException as e:
            print(f"⚠️  Kubernetes API error: {e}")
        except Exception as e:
            print(f"⚠️  Kubernetes status check failed: {e}")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                now = datetime.now()
                
                # Update all metrics
                self.get_redis_metrics()
                self.get_database_status()
                self.get_kubernetes_status()
                
                # Update history for charts
                self.metrics_history['timestamps'].append(now.strftime('%H:%M:%S'))
                self.metrics_history['user_count'].append(self.current_status['online_users'])
                self.metrics_history['replica_count'].append(self.current_status['replicas']['desired'])
                self.metrics_history['ready_pods'].append(self.current_status['replicas']['ready'])
                
                # Calculate uptime
                uptime = now - self.start_time
                self.current_status['uptime'] = str(uptime).split('.')[0]  # Remove microseconds
                self.current_status['last_updated'] = now.strftime('%Y-%m-%d %H:%M:%S')
                
                print(f"[{now.strftime('%H:%M:%S')}] Users: {self.current_status['online_users']}, "
                      f"Pods: {self.current_status['replicas']['ready']}/{self.current_status['replicas']['desired']}")
                
            except Exception as e:
                print(f"⚠️  Monitoring loop error: {e}")
            
            time.sleep(5)  # Update every 5 seconds

# Initialize monitor
monitor = ChatMonitor()

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def api_status():
    """API endpoint for current status"""
    return jsonify(monitor.current_status)

@app.route('/api/metrics')
def api_metrics():
    """API endpoint for metrics history"""
    return jsonify({
        'timestamps': list(monitor.metrics_history['timestamps']),
        'user_count': list(monitor.metrics_history['user_count']),
        'replica_count': list(monitor.metrics_history['replica_count']),
        'ready_pods': list(monitor.metrics_history['ready_pods'])
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    health_status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'redis': monitor.current_status['redis_status'] == 'connected',
            'database': monitor.current_status['database_status'] == 'connected',
            'kubernetes': bool(monitor.k8s_apps_v1),
            'autoscaler': monitor.current_status['autoscaler_status'] == 'running'
        }
    }
    
    # Overall health based on components
    unhealthy_components = [k for k, v in health_status['components'].items() if not v]
    if unhealthy_components:
        health_status['status'] = 'degraded'
        health_status['issues'] = unhealthy_components
    
    return jsonify(health_status)

if __name__ == '__main__':
    print("Starting Chat Server Monitoring Dashboard...")
    print(f"Dashboard will be available at: http://localhost:5000")
    print(f"Health check endpoint: http://localhost:5000/api/health")
    print(f"Monitoring namespace: {monitor.namespace}")
    print("Press Ctrl+C to stop")
    
    app.run(host='0.0.0.0', port=5001, debug=False)