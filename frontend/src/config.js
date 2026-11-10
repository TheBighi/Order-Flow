const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'localhost:8000'
const secure = window.location.protocol === 'https:'

export const API_BASE_URL = `${secure ? 'https' : 'http'}://${BACKEND_URL}`
export const WS_BASE_URL = `${secure ? 'wss' : 'ws'}://${BACKEND_URL}`
