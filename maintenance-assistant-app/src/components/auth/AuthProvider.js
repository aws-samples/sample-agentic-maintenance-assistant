import React, { createContext, useContext, useEffect, useState } from 'react';
import { Amplify } from 'aws-amplify';
import { getCurrentUser, signOut, fetchAuthSession } from 'aws-amplify/auth';

// This will be populated from runtime config
const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isConfigured, setIsConfigured] = useState(false);

  useEffect(() => {
    configureAmplify();
  }, []);

  const configureAmplify = async () => {
    try {
      // Fetch Cognito configuration from backend
      const response = await fetch('http://localhost:5001/api/auth/config');
      const config = await response.json();
      
      if (config.success) {
        Amplify.configure({
          Auth: {
            Cognito: {
              userPoolId: config.userPoolId,
              userPoolClientId: config.userAppClientId,
              identityPoolId: config.identityPoolId,
              loginWith: {
                email: true,
                username: true
              },
              signUpVerificationMethod: 'code',
              userAttributes: {
                email: {
                  required: true
                }
              },
              allowGuestAccess: false,
              passwordFormat: {
                minLength: 8,
                requireLowercase: true,
                requireUppercase: true,
                requireNumbers: true,
                requireSpecialCharacters: true
              }
            }
          }
        });
        
        setIsConfigured(true);
        await checkAuthState();
      }
    } catch (error) {
      console.error('Failed to configure Amplify:', error);
      setLoading(false);
    }
  };

  const checkAuthState = async () => {
    try {
      setLoading(true);
      const currentUser = await getCurrentUser();
      
      // Try to get session with AWS credentials
      let session;
      let hasAwsCredentials = false;
      
      try {
        session = await fetchAuthSession();
        hasAwsCredentials = !!(session.credentials && session.credentials.accessKeyId);
        console.log('AWS credentials available:', hasAwsCredentials);
      } catch (sessionError) {
        console.warn('Failed to get AWS credentials, using basic auth:', sessionError.message);
        // Continue with basic authentication
        session = { tokens: null };
      }
      
      setUser({
        username: currentUser.username,
        email: currentUser.signInDetails?.loginId || currentUser.attributes?.email,
        attributes: currentUser.attributes,
        isAuthenticated: true,
        tokens: session.tokens,
        hasAwsCredentials
      });
      
      console.log('Authentication successful');
      
    } catch (error) {
      console.log('Auth check failed:', error.message);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    try {
      await signOut();
      setUser(null);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const value = {
    user,
    loading,
    isConfigured,
    logout,
    checkAuthState
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};