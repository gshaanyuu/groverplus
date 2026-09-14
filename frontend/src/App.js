import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import { LayoutDashboard, Package, Users, ShoppingBag, LogOut, Plus, Search, ArrowUpRight, MapPin, ChevronDown, Check, X } from "lucide-react";
import "@/App.css";
import "@/fixes.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
axios.defaults.withCredentials = true;
const money = (n) => `₹${Number(n).toLocaleString("en-IN")}`;
const initials = (name = "") => name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase() || "S";

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
function beginGoogleLogin() {
  const redirectUrl = window.location.origin + "/dashboard";
  window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
}

function Login() {
  return (
    <main className="login-page">
      <div className="login-art">
        <div className="brand-mark">grove<span>+</span></div>
        <div className="art-copy">
          <p className="eyebrow">SELLER OPERATIONS</p>
          <h1>Your neighborhood,<br /><em>beautifully stocked.</em></h1>
          <p>One calm workspace for every customer, product and order in your society.</p>
        </div>
        <div className="art-note"><span>✦</span> Trusted by local sellers</div>
      </div>
      <section className="login-box">
        <div className="mobile-brand brand-mark">grove<span>+</span></div>
        <p className="eyebrow">WELCOME BACK</p>
        <h2>Sign in to your<br /><strong>seller workspace</strong></h2>
        <p className="muted">Continue with your Google account to access the dashboard.</p>
        <button data-testid="google-login-btn" className="primary-btn login-btn google-btn" onClick={beginGoogleLogin}>
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.5 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.8 1.1 8 3l5.7-5.7C33.9 6.2 29.2 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.8 15.1 19 12 24 12c3 0 5.8 1.1 8 3l5.7-5.7C33.9 6.2 29.2 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35 26.7 36 24 36c-5.3 0-9.7-3.5-11.3-8.3l-6.5 5C9.6 39.7 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.1 5.6l6.2 5.2C41.3 35.5 44 30.1 44 24c0-1.2-.1-2.4-.4-3.5z"/></svg>
          Continue with Google
          <ArrowUpRight size={17} />
        </button>
        <p className="fine-print">By continuing, you agree to Grove's seller terms.</p>
      </section>
    </main>
  );
}

function AuthCallback() {
  const location = useLocation();
  const navigate = useNavigate();
  const processed = useRef(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;
    const hash = location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) { navigate("/", { replace: true }); return; }
    const sessionId = decodeURIComponent(match[1]);
    (async () => {
      try {
        const r = await axios.post(`${API}/auth/session`, { session_id: sessionId });
        window.history.replaceState({}, "", "/dashboard");
        navigate("/dashboard", { replace: true, state: { user: r.data } });
      } catch (e) {
        setError("Sign in failed. Please try again.");
        setTimeout(() => navigate("/", { replace: true }), 1600);
      }
    })();
  }, [location.hash, navigate]);

  return (
    <div className="loading-screen" data-testid="auth-callback-screen">
      <div className="loading-mark">grove<span>+</span></div>
      <p>{error || "Signing you in…"}</p>
    </div>
  );
}

const initialForm = { name: "", category: "Dairy", price: "", stock: "", available: true };

function Dashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const [seller, setSeller] = useState(location.state?.user || null);
  const [authChecked, setAuthChecked] = useState(Boolean(location.state?.user));
  const [tab, setTab] = useState("Overview");
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showProduct, setShowProduct] = useState(false);
  const [showCustomer, setShowCustomer] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [editingCustomer, setEditingCustomer] = useState(null);
  const [form, setForm] = useState(initialForm);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [cart, setCart] = useState({});
  const [society, setSociety] = useState("All societies");

  useEffect(() => {
    if (seller) return;
    (async () => {
      try {
        const r = await axios.get(`${API}/auth/me`);
        setSeller(r.data);
      } catch {
        navigate("/", { replace: true });
      } finally {
        setAuthChecked(true);
      }
    })();
  }, [seller, navigate]);

  const load = async () => {
    try {
      const [p, c, o] = await Promise.all([
        axios.get(`${API}/products`),
        axios.get(`${API}/customers`),
        axios.get(`${API}/orders`),
      ]);
      setProducts(p.data); setCustomers(c.data); setOrders(o.data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { if (seller) load(); }, [seller]);

  const logout = async () => {
    try { await axios.post(`${API}/auth/logout`); } catch {}
    setSeller(null);
    navigate("/", { replace: true });
  };

  const saveProduct = async () => {
    const data = { ...form, price: +form.price, stock: +form.stock };
    if (editingProduct) await axios.put(`${API}/products/${editingProduct.id}`, data);
    else await axios.post(`${API}/products`, data);
    setShowProduct(false); setEditingProduct(null); setForm(initialForm); load();
  };
  const saveCustomer = async () => {
    if (editingCustomer) await axios.put(`${API}/customers/${editingCustomer.id}`, form);
    else await axios.post(`${API}/customers`, form);
    setShowCustomer(false); setEditingCustomer(null); setForm(initialForm); load();
  };
  const editProduct = (p) => { setEditingProduct(p); setForm(p); setShowProduct(true); };
  const editCustomer = (c) => { setEditingCustomer(c); setForm({ ...c, society: c.society || "Prestige Ozone" }); setShowCustomer(true); };

  const cartItems = useMemo(() => Object.entries(cart)
    .filter(([, q]) => q > 0)
    .map(([id, q]) => { const p = products.find(x => x.id === id); return p ? { ...p, quantity: q } : null; })
    .filter(Boolean), [cart, products]);
  const total = cartItems.reduce((s, p) => s + p.price * p.quantity, 0);

  const placeOrder = async () => {
    const c = customers.find(x => x.id === selected);
    if (!c || !cartItems.length) return;
    await axios.post(`${API}/orders`, {
      customer_id: c.id, customer_name: c.name, society: c.society,
      items: cartItems.map(p => ({ product_id: p.id, name: p.name, quantity: p.quantity, price: p.price })), total,
    });
    setCart({}); setSelected(""); load(); setTab("Orders");
  };

  if (!authChecked || (seller && loading)) {
    return (
      <div className="loading-screen" data-testid="workspace-loading">
        <div className="loading-mark">grove<span>+</span></div>
        <p>Preparing your workspace…</p>
      </div>
    );
  }
  if (!seller) return null;

  const visibleProducts = products.filter(p => p.name.toLowerCase().includes(search.toLowerCase()));
  const stats = [
    { label: "Revenue this month", value: money(orders.reduce((s, o) => s + o.total, 0) || 28460), change: "+12.8%", icon: "₹" },
    { label: "Active products", value: products.length || 4, change: "in catalogue", icon: "▦" },
    { label: "Customers served", value: customers.length || 128, change: "across 5 societies", icon: "◎" },
  ];
  const navItems = [
    { n: "Overview", i: LayoutDashboard },
    { n: "Inventory", i: Package },
    { n: "Customers", i: Users },
    { n: "Orders", i: ShoppingBag },
  ];

  return (
    <div className="app-shell">
      <aside>
        <div className="brand-mark">grove<span>+</span></div>
        <p className="side-label">WORKSPACE</p>
        {navItems.map(({ n, i: Icon }) => (
          <button key={n} data-testid={`nav-${n.toLowerCase()}`} className={tab === n ? "nav active" : "nav"} onClick={() => setTab(n)}>
            <Icon size={18} />{n}{n === "Orders" && orders.length > 0 && <b>{orders.length}</b>}
          </button>
        ))}
        <div className="side-bottom">
          <div className="seller-mini">
            {seller.picture ? <img className="avatar-img" src={seller.picture} alt={seller.name} /> : <div className="avatar">{initials(seller.name)}</div>}
            <div><b data-testid="seller-name">{seller.name}</b><small data-testid="seller-email">{seller.email}</small></div>
          </div>
          <button data-testid="seller-logout-btn" className="logout" onClick={logout}><LogOut size={16} /> Sign out</button>
        </div>
      </aside>
      <main className="content">
        <header>
          <div>
            <p className="eyebrow">{tab === "Overview" ? "MONDAY, 24 JUNE 2024" : "GROVE / " + tab.toUpperCase()}</p>
            <h1 data-testid="page-heading">{tab === "Overview" ? `Good morning, ${seller.name?.split(" ")[0] || "Seller"}` : tab}</h1>
          </div>
          <div className="header-actions">
            <div className="society-pill"><MapPin size={16} /><span>All societies</span><ChevronDown size={14} /></div>
            {seller.picture ? <img className="avatar-img" src={seller.picture} alt={seller.name} /> : <div className="avatar">{initials(seller.name)}</div>}
          </div>
        </header>
        {tab === "Overview" && <Overview stats={stats} products={products} customers={customers} orders={orders} setTab={setTab} />}
        {tab === "Inventory" && <Inventory products={visibleProducts} search={search} setSearch={setSearch} onAdd={() => { setEditingProduct(null); setForm(initialForm); setShowProduct(true); }} onEdit={editProduct} />}
        {tab === "Customers" && <CustomersTab customers={customers} society={society} setSociety={setSociety} onAdd={() => { setEditingCustomer(null); setForm({ ...initialForm, society: "Prestige Ozone" }); setShowCustomer(true); }} onEdit={editCustomer} />}
        {tab === "Orders" && <OrdersTab orders={orders} customers={customers} products={products} selected={selected} setSelected={setSelected} cart={cart} setCart={setCart} cartItems={cartItems} total={total} placeOrder={placeOrder} load={load} />}
        {showProduct && <Modal title={editingProduct ? "Update product" : "Add a product"} close={() => { setShowProduct(false); setEditingProduct(null); }}><FormProduct form={form} setForm={setForm} submit={saveProduct} /></Modal>}
        {showCustomer && <Modal title={editingCustomer ? "Update customer" : "Add a customer"} close={() => { setShowCustomer(false); setEditingCustomer(null); }}><FormCustomer form={form} setForm={setForm} submit={saveCustomer} /></Modal>}
      </main>
    </div>
  );
}

function Overview({ stats, products, customers, orders, setTab }) {
  return (
    <>
      <section className="welcome-band">
        <div>
          <p className="eyebrow light">TODAY'S SNAPSHOT</p>
          <h2>Small moments,<br /><em>big impact.</em></h2>
          <p>Keep your society shelves full and your customers happy.</p>
        </div>
        <div className="band-image" />
      </section>
      <div className="stats-grid">
        {stats.map(s => (
          <div key={s.label} className="stat" data-testid={`stat-${s.label.toLowerCase().replaceAll(" ", "-")}`}>
            <div className="stat-icon">{s.icon}</div>
            <small>{s.label}</small>
            <strong>{s.value}</strong>
            <span>{s.change}</span>
          </div>
        ))}
      </div>
      <div className="section-head"><div><p className="eyebrow">QUICK ACCESS</p><h2>Run your day</h2></div></div>
      <div className="quick-grid">
        <button data-testid="quick-inventory-btn" onClick={() => setTab("Inventory")}><Package /><span><b>Update inventory</b><small>{products.length} products need your attention</small></span><ArrowUpRight /></button>
        <button data-testid="quick-order-btn" onClick={() => setTab("Orders")}><ShoppingBag /><span><b>Place an order</b><small>Order for a customer in seconds</small></span><ArrowUpRight /></button>
        <button data-testid="quick-customer-btn" onClick={() => setTab("Customers")}><Users /><span><b>View customers</b><small>{customers.length} customers across societies</small></span><ArrowUpRight /></button>
      </div>
      <div className="section-head recent"><div><p className="eyebrow">RECENT ACTIVITY</p><h2>Latest orders</h2></div><button data-testid="view-all-orders-btn" className="text-btn" onClick={() => setTab("Orders")}>View all <ArrowUpRight size={15} /></button></div>
      <OrderList orders={orders.slice(0, 3)} />
    </>
  );
}

function Inventory({ products, search, setSearch, onAdd, onEdit }) {
  const [stockValues, setStockValues] = useState({});
  const valueFor = p => stockValues[p.id] ?? p.stock;
  const saveStock = async (p, value) => {
    const next = Math.max(0, Number(value) || 0);
    setStockValues(prev => ({ ...prev, [p.id]: next }));
    await axios.put(`${API}/products/${p.id}`, { ...p, stock: next });
  };
  return (
    <>
      <div className="toolbar">
        <div className="search"><Search size={17} /><input data-testid="inventory-search-input" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search products" /></div>
        <button data-testid="add-product-btn" className="primary-btn" onClick={onAdd}><Plus size={17} /> Add product</button>
      </div>
      <div className="product-grid">
        {products.map(p => (
          <div key={p.id} className="product-card" data-testid={`product-card-${p.id}`}>
            <div className="product-art"><span>{p.category === "Dairy" ? "🥛" : p.category === "Produce" ? "🍌" : "🍞"}</span><i className={p.available ? "available" : "unavailable"} /></div>
            <div className="product-info">
              <small>{p.category}</small>
              <h3>{p.name}</h3>
              <div className="product-price-row"><b>{money(p.price)}</b><span className={valueFor(p) < 10 ? "low" : "stock"}>{valueFor(p)} in stock</span></div>
              <div className="stock-editor">
                <button data-testid={`stock-decrease-${p.id}`} aria-label={`Decrease ${p.name} stock`} onClick={() => saveStock(p, valueFor(p) - 1)}>−</button>
                <input data-testid={`stock-quantity-${p.id}`} aria-label={`${p.name} stock quantity`} type="number" min="0" value={valueFor(p)} onChange={e => setStockValues(prev => ({ ...prev, [p.id]: e.target.value }))} onBlur={e => saveStock(p, e.target.value)} />
                <button data-testid={`stock-increase-${p.id}`} aria-label={`Increase ${p.name} stock`} onClick={() => saveStock(p, valueFor(p) + 1)}>+</button>
              </div>
              <button data-testid={`edit-product-${p.id}`} className="edit-link" onClick={() => onEdit(p)}>Edit price & availability <ArrowUpRight size={13} /></button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

const SOCIETY_FILTERS = ["All societies", "Prestige Ozone", "Palm Meadows", "Brigade Gateway", "Sobha Dream Acres", "Godrej Woods"];

function CustomersTab({ customers, society, setSociety, onAdd, onEdit }) {
  const list = customers.filter(c => society === "All societies" || c.society === society);
  return (
    <>
      <div className="toolbar">
        <div className="filter-tabs">
          {SOCIETY_FILTERS.map(s => (
            <button key={s} data-testid={`society-filter-${s.toLowerCase().replaceAll(" ", "-")}`} className={society === s ? "selected" : ""} onClick={() => setSociety(s)}>{s}</button>
          ))}
        </div>
        <button data-testid="add-customer-btn" className="primary-btn" onClick={onAdd}><Plus size={17} /> Add customer</button>
      </div>
      <div className="customer-list">
        {list.map(c => (
          <div key={c.id} className="customer-row" data-testid={`customer-row-${c.id}`}>
            <div className="avatar soft">{initials(c.name)}</div>
            <div className="customer-main"><b>{c.name}</b><span>{c.phone} · {c.address}</span></div>
            <span className="society-tag"><MapPin size={13} />{c.society}</span>
            <button data-testid={`edit-customer-${c.id}`} className="icon-btn" onClick={() => onEdit(c)}><ArrowUpRight size={17} /></button>
          </div>
        ))}
      </div>
    </>
  );
}

function OrdersTab({ orders, customers, products, selected, setSelected, cart, setCart, cartItems, total, placeOrder, load }) {
  const [statusBusy, setStatusBusy] = useState("");
  const changeStatus = async (id, status) => {
    setStatusBusy(id);
    await axios.patch(`${API}/orders/${id}/status`, null, { params: { status } });
    await load();
    setStatusBusy("");
  };
  return (
    <>
      <div className="order-layout">
        <section className="order-builder">
          <div className="section-head"><div><p className="eyebrow">NEW ORDER</p><h2>Shop for a customer</h2></div></div>
          <label>Select customer</label>
          <select data-testid="customer-select" value={selected} onChange={e => setSelected(e.target.value)}>
            <option value="">Choose customer</option>
            {customers.map(c => (<option key={c.id} value={c.id}>{c.name} · {c.society}</option>))}
          </select>
          <label>Add products</label>
          <div className="order-products">
            {products.map(p => (
              <div key={p.id} className="order-product">
                <span>{p.name}<small>{money(p.price)} · {p.stock} available</small></span>
                <div className="stepper">
                  <button data-testid={`decrease-${p.id}`} onClick={() => setCart({ ...cart, [p.id]: Math.max(0, (cart[p.id] || 0) - 1) })}>−</button>
                  <b>{cart[p.id] || 0}</b>
                  <button data-testid={`increase-${p.id}`} disabled={p.stock <= 0 || cart[p.id] >= p.stock} onClick={() => setCart({ ...cart, [p.id]: Math.min(p.stock, (cart[p.id] || 0) + 1) })}>+</button>
                </div>
              </div>
            ))}
          </div>
        </section>
        <div className="order-summary">
          <p className="eyebrow">ORDER SUMMARY</p>
          <h3>{selected ? customers.find(c => c.id === selected)?.name : "No customer selected"}</h3>
          {cartItems.length ? (
            <>
              {cartItems.map(p => (<div key={p.id} className="summary-line"><span>{p.name} × {p.quantity}</span><b>{money(p.price * p.quantity)}</b></div>))}
              <div className="total"><span>Total</span><b>{money(total)}</b></div>
              <button data-testid="place-order-btn" className="primary-btn full" onClick={placeOrder}>Place order <ArrowUpRight size={17} /></button>
            </>
          ) : (
            <p className="empty-summary">Choose a customer and add products to see the total.</p>
          )}
        </div>
      </div>
      <div className="section-head recent"><div><p className="eyebrow">ORDER HISTORY</p><h2>Recent orders</h2></div></div>
      <OrderList orders={orders} changeStatus={changeStatus} statusBusy={statusBusy} />
    </>
  );
}

function OrderList({ orders, changeStatus, statusBusy }) {
  return (
    <div className="order-list">
      {orders.length ? orders.map(o => (
        <div key={o.id} className="order-row" data-testid={`order-row-${o.id}`}>
          <b>{o.id}</b>
          <span>{o.customer_name}<small>{o.society}</small></span>
          <strong>{money(o.total)}</strong>
          {changeStatus ? (
            <select data-testid={`order-status-${o.id}`} className={`status-select ${o.status.toLowerCase().replaceAll(" ", "-")}`} disabled={statusBusy === o.id} value={o.status} onChange={e => changeStatus(o.id, e.target.value)}>
              <option value="Pending">Pending</option>
              <option value="Out for Delivery">Out for Delivery</option>
              <option value="Delivered">Delivered</option>
            </select>
          ) : (
            <span className={`status-select ${o.status.toLowerCase().replaceAll(" ", "-")}`}>{o.status}</span>
          )}
          <span className="date">{new Date(o.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</span>
        </div>
      )) : <div className="empty-summary">No orders yet.</div>}
    </div>
  );
}

function Modal({ title, close, children }) {
  return (
    <div className="modal-backdrop">
      <div className="modal">
        <button data-testid="modal-close-btn" className="modal-close" onClick={close}><X /></button>
        <p className="eyebrow">GROVE / NEW</p>
        <h2>{title}</h2>
        {children}
      </div>
    </div>
  );
}

function FormProduct({ form, setForm, submit }) {
  return (
    <div className="form-grid">
      {[["name", "Product name", "text"], ["price", "Price (₹)", "number"], ["stock", "Stock quantity", "number"]].map(([k, l, t]) => (
        <label key={k}>{l}<input data-testid={`product-${k}-input`} type={t} value={form[k] || ""} onChange={e => setForm({ ...form, [k]: e.target.value })} /></label>
      ))}
      <label>Category<select data-testid="product-category-input" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}>
        <option value="Dairy">Dairy</option>
        <option value="Produce">Produce</option>
        <option value="Bakery">Bakery</option>
        <option value="Pantry">Pantry</option>
      </select></label>
      <label className="availability-toggle"><span>Available for ordering</span><input data-testid="product-availability-input" type="checkbox" checked={form.available !== false} onChange={e => setForm({ ...form, available: e.target.checked })} /></label>
      <button data-testid="save-product-btn" className="primary-btn full" onClick={submit}>Save product <Check size={16} /></button>
    </div>
  );
}

function FormCustomer({ form, setForm, submit }) {
  return (
    <div className="form-grid">
      {[["name", "Full name"], ["phone", "Phone number"], ["address", "Address"]].map(([k, l]) => (
        <label key={k}>{l}<input data-testid={`customer-${k}-input`} value={form[k] || ""} onChange={e => setForm({ ...form, [k]: e.target.value })} /></label>
      ))}
      <label>Society<select data-testid="customer-society-input" value={form.society || "Prestige Ozone"} onChange={e => setForm({ ...form, society: e.target.value })}>
        <option value="Prestige Ozone">Prestige Ozone</option>
        <option value="Palm Meadows">Palm Meadows</option>
        <option value="Brigade Gateway">Brigade Gateway</option>
        <option value="Sobha Dream Acres">Sobha Dream Acres</option>
        <option value="Godrej Woods">Godrej Woods</option>
      </select></label>
      <button data-testid="save-customer-btn" className="primary-btn full" onClick={submit}>Save customer <Check size={16} /></button>
    </div>
  );
}

function AppRouter() {
  const location = useLocation();
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Login />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRouter />
    </BrowserRouter>
  );
}
