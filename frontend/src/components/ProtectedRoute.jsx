import { Navigate } from 'react-router-dom';
import authService from '../services/authService';

/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */
function ProtectedRoute({ children }) {
  const isAuthenticated = authService.isAuthenticated();

  if (!isAuthenticated) {
    // Redirect to login page
    return <Navigate to="/login" replace />;
  }

  return children;
}

export default ProtectedRoute;
