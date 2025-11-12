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
      
      // Try to get session - first without credentials, then with
      let session = { tokens: null };
      let hasAwsCredentials = false;
      
      try {
        // Try to get just the tokens first (no AWS credentials needed)
        console.log('Fetching auth session...');
        const authSession = await fetchAuthSession({ forceRefresh: true });
        
        console.log('Session retrieved, checking structure...');
        console.log('Session keys:', Object.keys(authSession));
        
        if (authSession.tokens) {
          session = authSession;
          console.log('✓ Tokens found in session');
          console.log('Token keys:', Object.keys(authSession.tokens));
          
          const idToken = authSession.tokens.idToken?.toString();
          const accessToken = authSession.tokens.accessToken?.toString();
          console.log('ID Token:', idToken ? `present (${idToken.substring(0, 20)}...)` : 'MISSING');
          console.log('Access Token:', accessToken ? 'present' : 'MISSING');
        } else {
          console.error('✗ No tokens in session!');
          console.error('Session structure:', JSON.stringify(authSession, null, 2));
        }
        
        hasAwsCredentials = !!(authSession.credentials && authSession.credentials.accessKeyId);
        console.log('AWS credentials:', hasAwsCredentials ? 'available' : 'not available');
        
      } catch (sessionError) {
        console.error('✗ Failed to fetch session:', sessionError.message);
        console.error('Error details:', sessionError);
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
      console.log('User object set with tokens:', session.tokens ? 'yes' : 'no');
      
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