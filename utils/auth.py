"""
Authentication Module for VisionGuard AI

Handles user authentication, JWT token generation/validation, and password hashing.
Implements secure authentication with access and refresh tokens.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this-in-production-use-env-file")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in token (typically user_id, email)
        expires_delta: Token expiration time (default: ACCESS_TOKEN_EXPIRE_MINUTES)
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": expire,
        "type": "access"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Data to encode in token (typically user_id)
        
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Dependency to get current authenticated user from JWT token.
    
    Args:
        credentials: HTTP Bearer token from request
        
    Returns:
        User data from token payload
        
    Raises:
        HTTPException: If token is invalid, expired, or not an access token
    """
    token = credentials.credentials
    
    # Decode token
    payload = decode_token(token)
    
    # Verify it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user data
    user_id: str = payload.get("sub")
    email: str = payload.get("email")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": user_id,
        "email": email,
        "full_name": payload.get("full_name"),
    }


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[Dict]:
    """
    Optional dependency to get current user (doesn't fail if no token).
    Useful for endpoints that work both with and without authentication.
    
    Args:
        credentials: Optional HTTP Bearer token
        
    Returns:
        User data if authenticated, None otherwise
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def validate_refresh_token(token: str) -> Dict:
    """
    Validate a refresh token and extract user data.
    
    Args:
        token: JWT refresh token
        
    Returns:
        User data from token
        
    Raises:
        HTTPException: If token is invalid or not a refresh token
    """
    payload = decode_token(token)
    
    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    return {"user_id": user_id}


def create_token_pair(user_id: str, email: str, full_name: str) -> Dict[str, str]:
    """
    Create both access and refresh tokens for a user.
    
    Args:
        user_id: User's ID
        email: User's email
        full_name: User's full name
        
    Returns:
        Dictionary with access_token and refresh_token
    """
    token_data = {
        "sub": user_id,
        "email": email,
        "full_name": full_name
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"sub": user_id})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
