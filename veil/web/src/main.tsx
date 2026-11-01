import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { Desk } from './site/Desk';
import { Landing } from './site/Landing';
import './site/site.css';

/** Hash routes keep the site deployable as static files: #/ (landing) and #/desk?run=<id> (review desk). */
function parse() {
  const [path, query] = (location.hash.replace(/^#/, '') || '/').split('?');
  return { path, run: new URLSearchParams(query).get('run')?.replace(/[^a-z0-9-]/gi, '') || new URLSearchParams(location.search).get('run') || 'c2' };
}

function App() {
  const [route, setRoute] = useState(parse);
  useEffect(() => {
    const on = () => {
      const next = parse();
      setRoute(prev => { if (next.path.startsWith('/') && (prev.path !== next.path || prev.run !== next.run)) window.scrollTo({ top: 0 }); return next; });
    };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  useEffect(() => { document.title = route.path === '/desk' ? `Review desk · ${route.run} · Veil` : 'Veil · See what your video gives away'; }, [route]);
  // in-page anchors (#how, #results) on the landing page scroll instead of routing
  if (!route.path.startsWith('/')) return <Landing />;
  return route.path === '/desk' || new URLSearchParams(location.search).has('run') ? <Desk key={route.run} run={route.run} /> : <Landing />;
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(<React.StrictMode><App /></React.StrictMode>);
