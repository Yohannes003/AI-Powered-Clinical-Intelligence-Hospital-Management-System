import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Global reset styles
const style = document.createElement('style');
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #060E1A; font-family: 'DM Sans', 'Segoe UI', -apple-system, sans-serif; }
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #0B1E3D; }
  ::-webkit-scrollbar-thumb { background: #1E3A5F; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #0EA5E9; }
  select option { background: #0B1E3D; color: #F1F5F9; }
  input[type=number]::-webkit-inner-spin-button { -webkit-appearance: none; }
`;
document.head.appendChild(style);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<React.StrictMode><App /></React.StrictMode>);
