import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Hub } from './App';
import './styles/tokens.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Hub />
  </StrictMode>,
);
