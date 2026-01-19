import axios from 'axios';

// API Configuration
// In development, the Vite proxy handles /api routes
// In production, set VITE_API_URL environment variable
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export default api;
