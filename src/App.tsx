import { type FormEvent, useEffect, useState } from 'react';

type OverviewResponse = {
  platform: string;
  health: {
    status: string;
    database: string;
    sessions: number;
    templates: number;
    healthy_vendors: number;
    redis_bus_enabled: boolean;
  };
  analytics: {
    generated_at: string;
    delivery_rate: number;
    avg_latency_ms: number;
    verified_sessions: number;
    blocked_sessions: number;
    total_sessions: number;
    channel_mix: Record<string, number>;
  };
  billing: {
    current_balance: number;
    currency: string;
    gst_rate: number;
    invoice_total: number;
    issued_invoices: number;
  };
  routes: Array<{
    name: string;
    channel: string;
    cost_per_message: number;
    latency_ms: number;
    healthy: boolean;
  }>;
};

type PublicOverviewResponse = {
  platform: string;
  health: OverviewResponse['health'];
  message?: string;
};

type AdminLoginResponse = {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  role: string;
  permissions: string[];
};

type AdminProfile = {
  username: string;
  role: string;
  permissions: string[];
};

type OtpRequestResponse = {
  session_id: string;
  destination: string;
  channel_used: 'sms' | 'email' | 'whatsapp';
  fallback_channels: Array<'sms' | 'email' | 'whatsapp'>;
  expires_at: string;
  sender_id: string;
  fraud_blocked: boolean;
  notes: string[];
  test_code?: string | null;
};

type OtpVerifyResponse = {
  verified: boolean;
  verified_at: string | null;
  webhook_signature: string | null;
  message: string;
};

const customerFeatures = [
  {
    title: 'Multi-Channel Failover',
    description:
      'Automatic fallback across SMS, Email, and WhatsApp to improve delivery probability and reduce verification friction.',
  },
  {
    title: 'Plug-and-Play SDKs',
    description:
      'Fast integration for Android, iOS, and Web teams with consistent APIs and straightforward onboarding.',
  },
  {
    title: 'Dynamic Templates',
    description:
      'Client-managed templates with multilingual content, reusable variables, and approval workflows.',
  },
  {
    title: 'Global Sender Identity',
    description:
      'Localized sender IDs and country-aware delivery settings for stronger trust and higher completion rates.',
  },
  {
    title: 'Real-Time Insights',
    description:
      'Operational dashboards for delivery rate, latency, success ratio, and health across all channels.',
  },
  {
    title: 'Secure Webhooks',
    description:
      'Immediate server-to-server notifications after OTP verification for downstream workflows and audit trails.',
  },
];

const adminCapabilities = [
  {
    title: 'AI Fraud Detection',
    description:
      'Continuously monitors traffic patterns to identify OTP pumping, bot spikes, and suspicious verification loops.',
  },
  {
    title: 'Least-Cost Routing',
    description:
      'Chooses the best-performing low-cost gateway in real time without sacrificing latency or reliability.',
  },
  {
    title: 'Automated Billing',
    description:
      'Credit management, invoice generation, and GST-aware tax handling for enterprise finance workflows.',
  },
  {
    title: 'Vendor Agnostic Infrastructure',
    description:
      'Switch between SMS and email providers without downtime to preserve service continuity under load.',
  },
  {
    title: 'Role-Based Access',
    description:
      'Granular permissions for support, finance, and operations teams with full action-level traceability.',
  },
];

const securityItems = [
  'AES-256 encryption in transit and at rest',
  'Rate limiting for numbers, accounts, and IP ranges',
  'Brute-force and replay protection',
  'Audit-ready event logging and retention policies',
];

const metrics = [
  { value: '99.9%', label: 'Target delivery uptime' },
  { value: '< 3s', label: 'Typical verification window' },
  { value: '3', label: 'Active fallback channels' },
  { value: '100%', label: 'Dashboard visibility' },
];

const workflow = [
  'Create a template and choose the preferred channel policy.',
  'Route traffic through the best gateway using live delivery signals.',
  'Verify the OTP and trigger secure webhook notifications instantly.',
  'Review analytics, billing, and fraud signals in the control center.',
];

const TOKEN_KEY = 'otp-admin-token';

function App() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [publicOverview, setPublicOverview] = useState<PublicOverviewResponse | null>(null);
  const [overviewError, setOverviewError] = useState<string | null>(null);

  const [adminUsername, setAdminUsername] = useState('');
  const [adminPassword, setAdminPassword] = useState('');
  const [adminToken, setAdminToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [adminProfile, setAdminProfile] = useState<AdminProfile | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);

  const [requestPhone, setRequestPhone] = useState('');
  const [requestEmail, setRequestEmail] = useState('');
  const [requestLocale, setRequestLocale] = useState('en');
  const [requestChannel, setRequestChannel] = useState<'sms' | 'email' | 'whatsapp'>('sms');
  const [requestTemplate, setRequestTemplate] = useState('default_otp');
  const [otpRequestResponse, setOtpRequestResponse] = useState<OtpRequestResponse | null>(null);
  const [otpRequestError, setOtpRequestError] = useState<string | null>(null);
  const [requestLoading, setRequestLoading] = useState(false);

  const [verifySessionId, setVerifySessionId] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [otpVerifyResponse, setOtpVerifyResponse] = useState<OtpVerifyResponse | null>(null);
  const [otpVerifyError, setOtpVerifyError] = useState<string | null>(null);
  const [verifyLoading, setVerifyLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadOverviewAndProfile() {
      try {
        if (adminToken) {
          const [overviewRes, profileRes] = await Promise.all([
            fetch('/api/v1/admin/overview', {
              signal: controller.signal,
              headers: { Authorization: `Bearer ${adminToken}` },
            }),
            fetch('/api/v1/admin/me', {
              signal: controller.signal,
              headers: { Authorization: `Bearer ${adminToken}` },
            }),
          ]);

          if (overviewRes.status === 401 || profileRes.status === 401) {
            localStorage.removeItem(TOKEN_KEY);
            setAdminToken(null);
            setAdminProfile(null);
            setOverview(null);
            setAuthError('Admin session expired. Please sign in again.');
            return;
          }

          if (!overviewRes.ok || !profileRes.ok) {
            throw new Error('Failed to load protected overview');
          }

          const overviewPayload = (await overviewRes.json()) as OverviewResponse;
          const profilePayload = (await profileRes.json()) as AdminProfile;
          setOverview(overviewPayload);
          setPublicOverview(null);
          setAdminProfile(profilePayload);
          setOverviewError(null);
          return;
        }

        const response = await fetch('/api/overview', { signal: controller.signal });
        if (!response.ok) {
          throw new Error(`Request failed with status ${response.status}`);
        }

        const payload = (await response.json()) as PublicOverviewResponse;
        setPublicOverview(payload);
        setOverview(null);
        setAdminProfile(null);
        setOverviewError(null);
      } catch (error) {
        if ((error as DOMException).name === 'AbortError') {
          return;
        }

        setOverviewError('Backend API is available after starting the FastAPI service. Admin data requires sign-in.');
      }
    }

    void loadOverviewAndProfile();

    return () => controller.abort();
  }, [adminToken]);

  async function loginAdmin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthLoading(true);
    setAuthError(null);
    try {
      const response = await fetch('/api/v1/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: adminUsername, password: adminPassword }),
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      const payload = (await response.json()) as AdminLoginResponse;
      localStorage.setItem(TOKEN_KEY, payload.access_token);
      setAdminToken(payload.access_token);
      setAuthError(null);
    } catch {
      setAuthError('Admin login failed. Check your credentials and try again.');
    } finally {
      setAuthLoading(false);
    }
  }

  function logoutAdmin() {
    localStorage.removeItem(TOKEN_KEY);
    setAdminToken(null);
    setAdminProfile(null);
    setOverview(null);
  }

  async function submitOtpRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setRequestLoading(true);
    setOtpRequestError(null);
    try {
      const response = await fetch('/api/v1/otp/request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: requestPhone,
          email: requestEmail,
          locale: requestLocale,
          preferred_channel: requestChannel,
          template_key: requestTemplate,
        }),
      });

      if (!response.ok) {
        throw new Error('OTP request failed');
      }

      const payload = (await response.json()) as OtpRequestResponse;
      setOtpRequestResponse(payload);
      setVerifySessionId(payload.session_id);
      setOtpRequestError(null);
    } catch {
      setOtpRequestError('Unable to request OTP right now.');
    } finally {
      setRequestLoading(false);
    }
  }

  async function submitOtpVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setVerifyLoading(true);
    setOtpVerifyError(null);
    try {
      const response = await fetch('/api/v1/otp/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: verifySessionId, code: verifyCode }),
      });

      if (!response.ok) {
        throw new Error('Verification failed');
      }

      const payload = (await response.json()) as OtpVerifyResponse;
      setOtpVerifyResponse(payload);
      setOtpVerifyError(null);
    } catch {
      setOtpVerifyError('OTP verification failed. Check session ID and code.');
    } finally {
      setVerifyLoading(false);
    }
  }

  const deliveryRate = overview ? `${overview.analytics.delivery_rate.toFixed(1)}%` : '99.2%';
  const averageLatency = overview ? `${overview.analytics.avg_latency_ms.toFixed(0)}ms` : '1.8s';
  const blockedSessions = overview ? `${overview.analytics.blocked_sessions}` : '0';
  const routeCount = overview ? `${overview.routes.length}` : '3';

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <main className="page">
        <header className="hero card">
          <div className="eyebrow">Advanced OTP and Authentication Service</div>
          <div className="hero-grid">
            <section className="hero-copy">
              <h1>Enterprise verification infrastructure built for reach, speed, and control.</h1>
              <p className="lead">
                A customer-facing OTP platform and administrator control center designed to improve delivery, reduce fraud,
                and keep operations compliant across global markets.
              </p>
              <div className="hero-actions">
                <a className="primary-action" href="#features">
                  Explore the platform
                </a>
                <a className="secondary-action" href="#operations">
                  Run live OTP demo
                </a>
              </div>
              <div className="hero-badges" aria-label="Platform highlights">
                <span>Multi-channel routing</span>
                <span>SDK ready</span>
                <span>Fraud monitoring</span>
                <span>GST billing</span>
              </div>
            </section>

            <aside className="dashboard card-inner" aria-label="Live status preview">
              <div className="dashboard-header">
                <span>Delivery Control Center</span>
                <span className="status-pill">{overview?.health.status ?? 'Live'}</span>
              </div>
              <div className="dashboard-meter">
                <div>
                  <strong>{overview?.platform ?? publicOverview?.platform ?? 'Realtime health'}</strong>
                  <p>
                    {overview
                      ? `${overview.health.sessions} sessions tracked across ${overview.health.healthy_vendors} healthy vendors`
                      : publicOverview?.message ?? 'Routing optimized across SMS, Email, and WhatsApp'}
                  </p>
                </div>
                <div className="meter-ring" aria-hidden="true">
                  <span>{overview ? `${Math.round(overview.analytics.delivery_rate)}%` : '96%'}</span>
                </div>
              </div>
              <div className="mini-grid">
                <div>
                  <span>Latency</span>
                  <strong>{averageLatency}</strong>
                </div>
                <div>
                  <span>Success rate</span>
                  <strong>{deliveryRate}</strong>
                </div>
                <div>
                  <span>Risk score</span>
                  <strong>{blockedSessions === '0' ? 'Low' : 'Monitored'}</strong>
                </div>
                <div>
                  <span>Fallback</span>
                  <strong>{routeCount} routes</strong>
                </div>
              </div>
              {overviewError ? <p className="live-note">{overviewError}</p> : null}
              {!overview && publicOverview ? (
                <p className="live-note">Sign in as admin to unlock analytics, billing, fraud, routes, and RBAC APIs.</p>
              ) : null}
              {overview ? (
                <div className="live-strip" aria-label="Live backend snapshot">
                  <span>API {overview.health.status}</span>
                  <span>{overview.analytics.verified_sessions} verified</span>
                  <span>{overview.billing.issued_invoices} invoices</span>
                </div>
              ) : null}
            </aside>
          </div>
        </header>

        <section id="operations" className="ops-layout">
          <article className="card ops-card">
            <div className="eyebrow">Admin access</div>
            <h2>Protected routes require authenticated admin sessions.</h2>
            {adminProfile ? (
              <div className="auth-state">
                <p>
                  Signed in as <strong>{adminProfile.username}</strong> ({adminProfile.role})
                </p>
                <p>Permissions: {adminProfile.permissions.join(', ')}</p>
                <button className="secondary-action" type="button" onClick={logoutAdmin}>
                  Logout
                </button>
              </div>
            ) : (
              <form className="ops-form" onSubmit={loginAdmin}>
                <label>
                  Admin username
                  <input
                    value={adminUsername}
                    onChange={(event) => setAdminUsername(event.target.value)}
                    placeholder="Enter admin username"
                    autoComplete="off"
                    required
                  />
                </label>
                <label>
                  Admin password
                  <input
                    type="password"
                    value={adminPassword}
                    onChange={(event) => setAdminPassword(event.target.value)}
                    placeholder="Enter admin password"
                    autoComplete="off"
                    required
                  />
                </label>
                <button className="primary-action" type="submit" disabled={authLoading}>
                  {authLoading ? 'Signing in...' : 'Admin sign in'}
                </button>
                {authError ? <p className="form-error">{authError}</p> : null}
              </form>
            )}
          </article>

          <article className="card ops-card">
            <div className="eyebrow">Live OTP panel</div>
            <h2>Request and verify OTP codes against the backend in real time.</h2>
            <div className="otp-grid">
              <form className="ops-form" onSubmit={submitOtpRequest}>
                <label>
                  Phone number
                  <input
                    value={requestPhone}
                    onChange={(event) => setRequestPhone(event.target.value)}
                    placeholder="+919876543210"
                    autoComplete="off"
                    required
                  />
                </label>
                <label>
                  Email
                  <input
                    type="email"
                    value={requestEmail}
                    onChange={(event) => setRequestEmail(event.target.value)}
                    placeholder="you@example.com"
                    autoComplete="off"
                    required
                  />
                </label>
                <div className="ops-row">
                  <label>
                    Locale
                    <input value={requestLocale} onChange={(event) => setRequestLocale(event.target.value)} required />
                  </label>
                  <label>
                    Preferred channel
                    <select
                      value={requestChannel}
                      onChange={(event) => setRequestChannel(event.target.value as 'sms' | 'email' | 'whatsapp')}
                    >
                      <option value="sms">sms</option>
                      <option value="email">email</option>
                      <option value="whatsapp">whatsapp</option>
                    </select>
                  </label>
                </div>
                <label>
                  Template key
                  <input value={requestTemplate} onChange={(event) => setRequestTemplate(event.target.value)} required />
                </label>
                <button className="primary-action" type="submit" disabled={requestLoading}>
                  {requestLoading ? 'Requesting...' : 'Request OTP'}
                </button>
                {otpRequestError ? <p className="form-error">{otpRequestError}</p> : null}
                {otpRequestResponse ? (
                  <div className="result-box">
                    <p>
                      Session: <strong>{otpRequestResponse.session_id}</strong>
                    </p>
                    <p>Channel: {otpRequestResponse.channel_used}</p>
                    <p>Destination: {otpRequestResponse.destination}</p>
                    {otpRequestResponse.test_code ? (
                      <p>
                        Test OTP code: <strong>{otpRequestResponse.test_code}</strong>
                      </p>
                    ) : null}
                    <p>Notes: {otpRequestResponse.notes.join(' | ')}</p>
                  </div>
                ) : null}
              </form>

              <form className="ops-form" onSubmit={submitOtpVerify}>
                <label>
                  Session ID
                  <input value={verifySessionId} onChange={(event) => setVerifySessionId(event.target.value)} required />
                </label>
                <label>
                  OTP code
                  <input value={verifyCode} onChange={(event) => setVerifyCode(event.target.value)} required />
                </label>
                <button className="primary-action" type="submit" disabled={verifyLoading}>
                  {verifyLoading ? 'Verifying...' : 'Verify OTP'}
                </button>
                {otpVerifyError ? <p className="form-error">{otpVerifyError}</p> : null}
                {otpVerifyResponse ? (
                  <div className="result-box">
                    <p>
                      Result: <strong>{otpVerifyResponse.message}</strong>
                    </p>
                    <p>Verified: {otpVerifyResponse.verified ? 'Yes' : 'No'}</p>
                    <p>Webhook signature: {otpVerifyResponse.webhook_signature ?? 'Not available'}</p>
                  </div>
                ) : null}
              </form>
            </div>
          </article>
        </section>

        <section className="stats-grid" aria-label="Key metrics">
          {metrics.map((metric) => (
            <article className="card metric-card" key={metric.label}>
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
            </article>
          ))}
        </section>

        <section id="features" className="section-stack">
          <div className="section-heading">
            <div>
              <div className="eyebrow">Customer-centric features</div>
              <h2>Everything needed for fast rollout and better OTP completion.</h2>
            </div>
            <p>
              From SDK adoption to multi-language templates, the platform is shaped around lower integration effort and
              higher verification success.
            </p>
          </div>

          <div className="card-grid">
            {customerFeatures.map((item) => (
              <article className="card feature-card" key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="split-layout">
          <article className="card detail-panel">
            <div className="eyebrow">Administrator capabilities</div>
            <h2>The control center for routing, fraud, billing, and access.</h2>
            <div className="stack-list">
              {adminCapabilities.map((item) => (
                <div className="stack-item" key={item.title}>
                  <div className="stack-title-row">
                    <h3>{item.title}</h3>
                    <span className="stack-tag">Enterprise</span>
                  </div>
                  <p>{item.description}</p>
                </div>
              ))}
            </div>
          </article>

          <aside className="card workflow-panel">
            <div className="eyebrow">Verification workflow</div>
            <h2>Simple from the end user, powerful behind the scenes.</h2>
            <ol>
              {workflow.map((step, index) => (
                <li key={step}>
                  <span>{index + 1}</span>
                  <p>{step}</p>
                </li>
              ))}
            </ol>
          </aside>
        </section>

        <section id="security" className="security-layout">
          <article className="card security-card">
            <div className="eyebrow">Security and compliance</div>
            <h2>Defense layers that support enterprise-grade verification.</h2>
            <ul>
              {securityItems.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>

          <article className="card template-panel">
            <div className="eyebrow">Operations snapshot</div>
            <div className="template-box">
              <div>
                <span className="template-label">Localized sender ID</span>
                <strong>GV-TECH</strong>
              </div>
              <div>
                <span className="template-label">Fraud watch</span>
                <strong>Monitoring bot spikes</strong>
              </div>
              <div>
                <span className="template-label">Webhook status</span>
                <strong>Verified events enabled</strong>
              </div>
              <div>
                <span className="template-label">Billing</span>
                <strong>GST ready invoicing</strong>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>
  );
}

export default App;
