import React, { useState } from 'react';
import { signIn, signUp, confirmSignUp, resetPassword, confirmResetPassword } from 'aws-amplify/auth';
import { useAuth } from './AuthProvider';

const LoginForm = ({ onSuccess }) => {
  const [mode, setMode] = useState('signin'); // signin, signup, confirm, forgot, reset
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    confirmationCode: '',
    newPassword: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const { checkAuthState } = useAuth();

  const handleInputChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
    setError('');
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const result = await signIn({
        username: formData.username,
        password: formData.password
      });
      
      // Wait a moment for the session to be established
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Trigger auth state check
      await checkAuthState();
      
      // Call success callback
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      if (error.message && error.message.includes('already a signed in user')) {
        // User is already signed in, just trigger auth state check
        await checkAuthState();
        if (onSuccess) {
          onSuccess();
        }
      } else {
        setError(error.message || 'Sign in failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    try {
      await signUp({
        username: formData.username,
        password: formData.password,
        options: {
          userAttributes: {
            email: formData.email
          }
        }
      });
      
      setMessage('Please check your email for the confirmation code');
      setMode('confirm');
    } catch (error) {
      setError(error.message || 'Sign up failed');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await confirmSignUp({
        username: formData.username,
        confirmationCode: formData.confirmationCode
      });
      
      setMessage('Account confirmed! Please sign in.');
      setMode('signin');
      setFormData({ ...formData, confirmationCode: '' });
    } catch (error) {
      setError(error.message || 'Confirmation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await resetPassword({ username: formData.username });
      setMessage('Password reset code sent to your email');
      setMode('reset');
    } catch (error) {
      setError(error.message || 'Password reset failed');
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    if (formData.newPassword !== formData.confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    try {
      await confirmResetPassword({
        username: formData.username,
        confirmationCode: formData.confirmationCode,
        newPassword: formData.newPassword
      });
      
      setMessage('Password reset successful! Please sign in with your new password.');
      setMode('signin');
      setFormData({ 
        ...formData, 
        confirmationCode: '', 
        newPassword: '', 
        confirmPassword: '',
        password: ''
      });
    } catch (error) {
      setError(error.message || 'Password reset confirmation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-form">
        <h2>
          {mode === 'signin' && 'Sign In'}
          {mode === 'signup' && 'Create Account'}
          {mode === 'confirm' && 'Confirm Account'}
          {mode === 'forgot' && 'Reset Password'}
          {mode === 'reset' && 'Set New Password'}
        </h2>

        {error && <div className="error-message">{error}</div>}
        {message && <div className="success-message">{message}</div>}

        {mode === 'signin' && (
          <form onSubmit={handleSignIn}>
            <input
              type="text"
              name="username"
              placeholder="Username or Email"
              value={formData.username}
              onChange={handleInputChange}
              required
            />
            <input
              type="password"
              name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleInputChange}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Signing In...' : 'Sign In'}
            </button>
            
            <div className="auth-links">
              <button type="button" onClick={() => setMode('signup')}>
                Create Account
              </button>
              <button type="button" onClick={() => setMode('forgot')}>
                Forgot Password?
              </button>
            </div>
          </form>
        )}

        {mode === 'signup' && (
          <form onSubmit={handleSignUp}>
            <input
              type="text"
              name="username"
              placeholder="Username"
              value={formData.username}
              onChange={handleInputChange}
              required
            />
            <input
              type="email"
              name="email"
              placeholder="Email"
              value={formData.email}
              onChange={handleInputChange}
              required
            />
            <input
              type="password"
              name="password"
              placeholder="Password"
              value={formData.password}
              onChange={handleInputChange}
              required
            />
            <input
              type="password"
              name="confirmPassword"
              placeholder="Confirm Password"
              value={formData.confirmPassword}
              onChange={handleInputChange}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>
            
            <div className="auth-links">
              <button type="button" onClick={() => setMode('signin')}>
                Already have an account? Sign In
              </button>
            </div>
          </form>
        )}

        {mode === 'confirm' && (
          <form onSubmit={handleConfirmSignUp}>
            <p>Enter the confirmation code sent to your email:</p>
            <input
              type="text"
              name="confirmationCode"
              placeholder="Confirmation Code"
              value={formData.confirmationCode}
              onChange={handleInputChange}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Confirming...' : 'Confirm Account'}
            </button>
            
            <div className="auth-links">
              <button type="button" onClick={() => setMode('signin')}>
                Back to Sign In
              </button>
            </div>
          </form>
        )}

        {mode === 'forgot' && (
          <form onSubmit={handleForgotPassword}>
            <p>Enter your username to reset your password:</p>
            <input
              type="text"
              name="username"
              placeholder="Username"
              value={formData.username}
              onChange={handleInputChange}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Sending...' : 'Send Reset Code'}
            </button>
            
            <div className="auth-links">
              <button type="button" onClick={() => setMode('signin')}>
                Back to Sign In
              </button>
            </div>
          </form>
        )}

        {mode === 'reset' && (
          <form onSubmit={handleResetPassword}>
            <p>Enter the reset code and your new password:</p>
            <input
              type="text"
              name="confirmationCode"
              placeholder="Reset Code"
              value={formData.confirmationCode}
              onChange={handleInputChange}
              required
            />
            <input
              type="password"
              name="newPassword"
              placeholder="New Password"
              value={formData.newPassword}
              onChange={handleInputChange}
              required
            />
            <input
              type="password"
              name="confirmPassword"
              placeholder="Confirm New Password"
              value={formData.confirmPassword}
              onChange={handleInputChange}
              required
            />
            <button type="submit" disabled={loading}>
              {loading ? 'Resetting...' : 'Reset Password'}
            </button>
            
            <div className="auth-links">
              <button type="button" onClick={() => setMode('signin')}>
                Back to Sign In
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default LoginForm;