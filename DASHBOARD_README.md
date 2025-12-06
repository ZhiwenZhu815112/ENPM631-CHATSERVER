# Chat Server Monitoring Dashboard 📊

A comprehensive web-based monitoring dashboard for the Chat Server application running on Kubernetes. This dashboard provides real-time visibility into your chat server pods, user activity, and system health.

## Features ✨

- **Real-time Monitoring**: Live updates every 5 seconds
- **Pod Management**: Monitor pod status, replica counts, and health
- **User Analytics**: Track online users and total registered users
- **Service Health**: Monitor Redis, PostgreSQL, and Autoscaler status
- **Interactive Charts**: Visualize user count and pod scaling over time
- **Responsive Design**: Works on desktop and mobile devices
- **RESTful API**: Programmatic access to monitoring data

## Screenshots

### Main Dashboard
The dashboard provides an overview of:
- Online user count and total registered users
- Active pod count and desired replicas
- Total messages sent through the system
- Dashboard uptime

### Service Status
Monitor the health of critical services:
- Redis connectivity and status
- PostgreSQL database connectivity
- Kubernetes autoscaler status
- Overall system health

### Real-time Charts
- User count over time (last 5 minutes)
- Pod scaling behavior
- Resource utilization trends

## Quick Start 🚀

### Prerequisites
- Python 3.7+
- Access to the same network as your Redis and PostgreSQL instances
- Kubernetes cluster access (optional, for K8s monitoring)

### 1. Install Dependencies
```bash
# Install dashboard-specific dependencies
pip install -r dashboard-requirements.txt
```

### 2. Run the Dashboard

**Linux/macOS:**
```bash
chmod +x start-dashboard.sh

./start-dashboard.sh
```

**Windows:**
```cmd
start-dashboard.bat
```

**Manual Start:**
```bash
python dashboard.py
```

### 3. Access the Dashboard
Open your browser and go to: **http://localhost:5000**

## Configuration 🔧

The dashboard can be configured using environment variables:

### Kubernetes Settings
```bash
export NAMESPACE=chat-app                    # K8s namespace to monitor
export DEPLOYMENT_NAME=chat-server           # Deployment name to monitor
```

### Redis Settings
```bash
export REDIS_HOST=localhost                  # Redis host
export REDIS_PORT=6379                       # Redis port  
export REDIS_PASSWORD=mypassword             # Redis password (if any)
```

### Database Settings
```bash
export DB_HOST=localhost                     # PostgreSQL host
export DB_PORT=5432                          # PostgreSQL port
export DB_NAME=chatdb                        # Database name
export DB_USER=chatuser                      # Database user
export DB_PASS=chatpass                      # Database password
```

### Example Configuration for Kubernetes
If your services are running in Kubernetes with port forwarding:

```bash
# Forward Redis port
kubectl port-forward svc/redis-service 6379:6379 -n chat-app

# Forward PostgreSQL port  
kubectl port-forward svc/postgres-service 5432:5432 -n chat-app

# Run dashboard with K8s monitoring
export NAMESPACE=chat-app
export DEPLOYMENT_NAME=chat-server
export REDIS_HOST=localhost
export DB_HOST=localhost
python dashboard.py
```

## API Endpoints 🔌

The dashboard exposes several API endpoints for programmatic access:

### `/api/status`
Returns current system status including:
- Online user count
- Pod replica information
- Service health status
- Total users and messages

### `/api/metrics`
Returns time-series data for charts:
- User count history
- Pod scaling history
- Timestamps for the last 5 minutes

### `/api/health`
Health check endpoint returning:
- Overall system health status
- Individual component health
- List of any unhealthy components

Example API usage:
```bash
# Get current status
curl http://localhost:5000/api/status

# Get metrics for charts
curl http://localhost:5000/api/metrics

# Health check
curl http://localhost:5000/api/health
```

## Dashboard Components 📋

### Metrics Overview
- **Online Users**: Current number of connected users
- **Active Pods**: Currently running and ready pods
- **Total Messages**: All-time message count from database
- **Uptime**: Dashboard uptime since last restart

### Service Status Indicators
- 🟢 Green: Service is healthy and connected
- 🟡 Yellow: Service has warnings or degraded performance
- 🔴 Red: Service is down or has errors
- ⚪ Gray: Service status unknown

### Pod Details Table
Detailed information about each chat server pod:
- Pod name and current phase
- Ready status and restart count
- Pod age and assigned node
- Internal IP address

### Online Users List
Real-time list of currently connected users with online indicators.

### Interactive Charts
- **User Count Over Time**: Shows user activity patterns
- **Pod Scaling**: Visualizes autoscaler behavior

## Troubleshooting 🛠️

### Common Issues

**1. Dashboard shows "Service status unknown"**
- Check that the service hostnames/IPs are correct
- Verify network connectivity to Redis and PostgreSQL
- Ensure credentials are correct

**2. Kubernetes monitoring not working**
- Verify kubectl is configured and accessible
- Check that the namespace and deployment names are correct
- Ensure proper RBAC permissions for the dashboard

**3. Charts not updating**
- Check browser console for JavaScript errors
- Verify the `/api/metrics` endpoint is accessible
- Clear browser cache and refresh

**4. Connection timeouts**
- Increase timeout values in `dashboard.py` if needed
- Check firewall rules between dashboard and services
- Verify service discovery/DNS resolution

### Debug Mode
To enable debug logging, modify `dashboard.py`:
```python
app.run(host='0.0.0.0', port=5000, debug=True)
```

### Logs
Monitor dashboard logs for connection issues and errors:
```bash
python dashboard.py 2>&1 | tee dashboard.log
```

## Architecture 📐

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Browser   │    │    Dashboard    │    │   Kubernetes    │
│                 │◄──►│     Flask       │◄──►│      API        │
│   (Port 5000)   │    │   Application   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        
                       ┌────────┴────────┐               
                       ▼                 ▼               
                ┌─────────────┐   ┌─────────────┐        
                │    Redis    │   │ PostgreSQL  │        
                │             │   │             │        
                │ (User State)│   │ (Messages)  │        
                └─────────────┘   └─────────────┘        
```

The dashboard operates as a standalone monitoring service that:
1. Connects to your existing Redis and PostgreSQL instances
2. Uses the Kubernetes API to monitor pod status
3. Provides a web interface for real-time monitoring
4. Stores short-term metrics in memory for charting

## Security Considerations 🔒

- The dashboard runs on localhost by default for security
- No authentication is built-in - use reverse proxy with auth if exposing externally
- Database and Redis credentials are passed via environment variables
- Kubernetes access uses your local kubeconfig or in-cluster config

## Contributing 🤝

To extend the dashboard:

1. **Add new metrics**: Modify the `ChatMonitor` class in `dashboard.py`
2. **Customize UI**: Edit `templates/dashboard.html`
3. **Add API endpoints**: Create new Flask routes in `dashboard.py`
4. **Enhance charts**: Modify the Chart.js configuration in the HTML template

## License 📄

This dashboard is part of the Chat Server project and follows the same license terms.




If you are running into issues with redis an postgres, apply port forwaring. Run the two following commands in their own terminals. 

kubectl port-forward -n chat-app service/redis-service 6379:6379
kubectl port-forward -n chat-app service/postgres-service 5432:5432
