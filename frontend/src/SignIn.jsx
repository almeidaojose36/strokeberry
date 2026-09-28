import React, {useState} from 'react';
import {ArrowRight, LoaderCircle, Mail, MailCheck} from 'lucide-react';
import {BRAND, BrandMark} from './brand.jsx';
import {sendEmailLink, signInWithGoogle} from './auth.js';

function GoogleLogo() {
  return <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>;
}

export default function SignIn({notice}) {
  const [email, setEmail] = useState(''), [busy, setBusy] = useState(''), [sent, setSent] = useState(false), [error, setError] = useState(notice || '');
  async function google() {
    setBusy('google'); setError('');
    try { await signInWithGoogle(); } catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  async function link(event) {
    event.preventDefault();
    if (!email.trim()) return;
    setBusy('email'); setError('');
    try { await sendEmailLink(email.trim()); setSent(true); } catch (e) { setError(e.message); } finally { setBusy(''); }
  }
  return <div className="sign-in-page">
    <section className="sign-in-card">
      <a className="sign-in-brand" href="/"><BrandMark size={72}/></a>
      <div className="eyebrow">Welcome to {BRAND.name}</div>
      {sent ? <>
        <span className="dialog-icon"><MailCheck size={26}/></span>
        <h1>Check your inbox</h1>
        <p>We sent a sign-in link to <strong>{email}</strong>. Open it on this device to continue. It can take a minute — check your spam folder too.</p>
        <button className="button ghost" onClick={() => setSent(false)}>Use a different email</button>
      </> : <>
        <h1>Sign in to start drawing</h1>
        <p>Your projects and videos are saved to your account. Your first 3 videos are free.</p>
        {error && <div className="sign-in-error" role="alert">{error}</div>}
        <button className="button google-button" onClick={google} disabled={Boolean(busy)}>
          {busy === 'google' ? <LoaderCircle size={18} className="spin"/> : <GoogleLogo/>}Continue with Google
        </button>
        <div className="sign-in-divider"><span>or</span></div>
        <form onSubmit={link} className="email-form">
          <label htmlFor="sign-in-email" className="field-label">Email address</label>
          <input id="sign-in-email" type="email" autoComplete="email" required placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)}/>
          <button className="button primary" type="submit" disabled={Boolean(busy)}>
            {busy === 'email' ? <LoaderCircle size={17} className="spin"/> : <Mail size={17}/>}Email me a sign-in link<ArrowRight size={16}/>
          </button>
        </form>
        <p className="sign-in-fine">No password needed.</p>
      </>}
    </section>
  </div>;
}
