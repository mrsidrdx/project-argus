# Aegis Gateway Frontend

A modern Next.js 15 admin dashboard for the Aegis Gateway policy management system.

## Features

- 🔐 **Authentication**: JWT-based login with token management
- 📊 **Dashboard**: Real-time overview of agents, policies, and decisions
- 👥 **Agent Management**: View and monitor all registered agents
- 📋 **Policy Monitoring**: Real-time policy version tracking and statistics
- 🔍 **Decision Tracking**: View recent policy decisions with approval workflow
- ⚡ **Testing Interface**: Built-in tool call testing with predefined scenarios
- 🔗 **Tracing Integration**: Direct links to Jaeger traces for debugging
- 📱 **Responsive Design**: Modern UI with Tailwind CSS 4

## Environment Configuration

Create a `.env.local` file in the frontend directory:

```bash
# API Configuration
NEXT_PUBLIC_API_BASE=http://localhost:8080

# Jaeger Tracing UI
NEXT_PUBLIC_JAEGER_URL=http://localhost:16686
```

## Development

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

## Authentication

Default development credentials:
- **Username**: `admin`
- **Password**: `admin123`

⚠️ **Important**: Change these credentials in production by setting the following environment variables in the backend:
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `JWT_SECRET_KEY`
- `ADMIN_API_KEY`

## Features Overview

### Dashboard Tabs

1. **Overview**: Key metrics and statistics
2. **Agents**: List of all registered agents
3. **Policies**: Policy configuration and version info
4. **Recent Decisions**: Real-time policy decisions with approval actions
5. **Testing**: Interactive tool call testing interface

### Testing Interface

The testing tab provides:
- **Quick Tests**: Predefined test scenarios for common use cases
- **Custom Tests**: Build your own test calls with any parameters
- **Real-time Results**: See immediate responses with proper status codes
- **Error Handling**: Clear error messages and rate limit feedback

### Approval Workflow

- View pending approvals in the decisions table
- One-click approval directly from the UI
- Automatic refresh to show updated status
- Integration with backend approval tracking

## Production Considerations

- Enable HTTPS in production
- Configure proper CORS settings
- Set secure JWT secrets
- Use environment-specific API endpoints
- Enable proper logging and monitoring

## Technology Stack

- **Next.js 15**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS 4**: Modern styling
- **Lucide React**: Beautiful icons
- **date-fns**: Date formatting and manipulation