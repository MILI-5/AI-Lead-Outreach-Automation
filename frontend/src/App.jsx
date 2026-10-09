
import { useCallback, useEffect, useState } from "react";
import {
  LayoutDashboard, Users, MessageSquare, Send, CalendarDays,
  RefreshCw, Search, CheckCircle2, Target, TrendingUp,
  AlertCircle, Sparkles, Clock, Eye
} from "lucide-react";
import "./App.css";

const API = "http://127.0.0.1:8000";

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`
    );
  }
  return data;
}

function App() {
  const [leads, setLeads] = useState([]);
  const [page, setPage] = useState("Dashboard");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyLead, setBusyLead] = useState(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [selectedLead, setSelectedLead] = useState("1");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);

  const [preview, setPreview] = useState("");
  const [outreachMessage, setOutreachMessage] = useState("");
  const [outreachHistory, setOutreachHistory] = useState([]);

  const [slots, setSlots] = useState([]);
  const [meetingTime, setMeetingTime] = useState("");
  const [meetingTitle, setMeetingTitle] = useState("Lead Discovery Meeting");
  const [meetingDuration, setMeetingDuration] = useState("30");
  const [meetingNotes, setMeetingNotes] = useState("");
  const [meetingResult, setMeetingResult] = useState(null);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api("/api/leads/");
      if (!Array.isArray(data)) throw new Error("Unexpected leads response.");
      setLeads(data);
      setSelectedLead((old) =>
        data.some((lead) => String(lead.id) === old)
          ? old
          : String(data[0]?.id ?? "")
      );
    } catch (e) {
      setError(`Could not load leads: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const leadId = Number(selectedLead);
  const selected = leads.find((lead) => lead.id === leadId);

  async function runAction(action, successMessage) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await loadLeads();
    } catch (e) {
      setError(e.message || "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function discoverLeads() {
    await runAction(async () => {
      const data = await api("/api/leads/discover", { method: "POST" });
      setNotice(
        `Discovery complete: ${data.created_count ?? 0} new leads; ` +
        `${data.skipped_duplicates ?? 0} duplicates skipped.`
      );
    }, "Discovery completed.");
  }

  async function qualifyLead(id) {
    setBusyLead(id);
    setError("");
    setNotice("");
    try {
      const data = await api(`/api/leads/${id}/qualify`, { method: "POST" });
      setNotice(`Lead #${id}: ${data.category || "qualification completed"}.`);
      await loadLeads();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyLead(null);
    }
  }

  async function loadChat() {
    if (!leadId) return;
    await runAction(async () => {
      const data = await api(`/api/leads/${leadId}/messages`);
      setChatMessages(data.messages || []);
    }, "Conversation history loaded.");
  }

  async function sendChat(event) {
    event.preventDefault();
    if (!chatInput.trim() || !leadId) return;
    const message = chatInput.trim();
    setBusy(true);
    setError("");
    try {
      const data = await api(`/api/leads/${leadId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      setChatMessages((old) => [
        ...old,
        { role: "user", message: data.user_message || message },
        { role: "assistant", message: data.ai_reply || "No reply returned." },
      ]);
      setChatInput("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function previewOutreach() {
    if (!leadId) return;
    await runAction(async () => {
      const data = await api(`/api/leads/${leadId}/outreach/preview`, {
        method: "POST",
      });
      const message =
        typeof data === "string"
          ? data
          : data.message || data.preview || data.draft ||
            JSON.stringify(data, null, 2);
      setPreview(message);
      setOutreachMessage(message);
    }, "Outreach preview generated.");
  }

  async function saveOutreach() {
    if (!leadId || !outreachMessage.trim()) {
      setError("Generate or enter an outreach message first.");
      return;
    }
    await runAction(async () => {
      await api(`/api/leads/${leadId}/outreach`, {
        method: "POST",
        body: JSON.stringify({
          channel: "telegram",
          message: outreachMessage.trim(),
        }),
      });
      await loadOutreach();
    }, "Outreach draft saved.");
  }

  async function sendTelegram() {
    if (!leadId) return;
    await runAction(async () => {
      const data = await api(`/api/leads/${leadId}/outreach/send-telegram`, {
        method: "POST",
      });
      setNotice(
        `Telegram outreach sent successfully. Message ID: ${
          data.telegram_message_id ?? "confirmed"
        }.`
      );
      await loadOutreach();
    }, "Telegram outreach sent successfully.");
  }

  async function loadOutreach() {
    if (!leadId) return;
    const data = await api(`/api/leads/${leadId}/outreach`);
    setOutreachHistory(data.outreach || []);
  }

  async function loadSlots() {
    await runAction(async () => {
      const data = await api("/api/leads/meetings/slots");
      const available = Array.isArray(data)
        ? data
        : data.slots || data.available_slots || [];
      setSlots(available);
      setMeetingTime("");
    }, "Available meeting slots loaded.");
  }

  async function bookMeeting(event) {
    event.preventDefault();
    if (!leadId || !meetingTime) {
      setError("Select a lead and an available meeting slot.");
      return;
    }
    await runAction(async () => {
      const data = await api("/api/leads/meetings/book", {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          meeting_time: meetingTime,
          duration_minutes: Number(meetingDuration),
          timezone: "Asia/Kolkata",
          meeting_title: meetingTitle,
          meeting_link: "",
          notes: meetingNotes,
        }),
      });
      setMeetingResult(data);
    }, "Meeting booked successfully.");
  }

  const filteredLeads = leads.filter((lead) =>
    [lead.name, lead.company_name, lead.industry, lead.location,
      lead.category, lead.status]
      .filter(Boolean).join(" ").toLowerCase().includes(search.toLowerCase())
  );

  const qualified = leads.filter((l) => l.category === "Qualified").length;
  const potential = leads.filter((l) => l.category === "Potential").length;
  const meetings = leads.filter((l) => l.status === "Meeting Scheduled").length;

  const navItems = [
    ["Dashboard", LayoutDashboard],
    ["Leads", Users],
    ["AI Conversations", MessageSquare],
    ["Outreach", Send],
    ["Meetings", CalendarDays],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">L</div>
          <div><h2>LeadPilot</h2><span>AI Outreach Platform</span></div>
        </div>
        <p className="nav-label">WORKSPACE</p>
        <nav>
          {navItems.map(([name, Icon]) => (
            <button key={name}
              className={`nav-item ${page === name ? "active" : ""}`}
              onClick={() => { setPage(name); setError(""); setNotice(""); }}>
              <Icon size={18} /><span>{name}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className={`status-dot ${error ? "offline" : ""}`} />
          <div><strong>Backend API</strong><span>{error ? "Check connection" : "Connection available"}</span></div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div><span className="eyebrow">WORKSPACE / {page.toUpperCase()}</span><h1>{page === "Dashboard" ? "Overview" : page}</h1></div>
          <button className="refresh-button" onClick={loadLeads} disabled={loading}>
            <RefreshCw size={16} />{loading ? "Refreshing..." : "Refresh data"}
          </button>
        </header>

        {error && <div className="error-banner"><AlertCircle size={18}/>{error}</div>}
        {notice && <div className="success-banner"><CheckCircle2 size={18}/>{notice}</div>}

        {page === "Dashboard" || page === "Leads" ? (
          <>
            <section className="welcome-panel">
              <div><span className="welcome-tag">AI-POWERED WORKFLOW</span>
                <h2>Turn prospects into opportunities.</h2>
                <p>Discover, qualify, contact and schedule meetings with your leads.</p></div>
              <div className="welcome-symbol"><Target size={42}/></div>
            </section>

            <section className="action-toolbar">
              <div><h2><Sparkles size={17}/> Lead actions</h2><p>Run lead discovery and AI qualification.</p></div>
              <div className="action-buttons">
                <button className="primary-action" disabled={busy} onClick={discoverLeads}>
                  <Search size={16}/>{busy ? "Working..." : "Discover leads"}
                </button>
                <button className="secondary-action" onClick={loadLeads} disabled={loading}>
                  <RefreshCw size={15}/>Refresh leads
                </button>
              </div>
            </section>

            <section className="stats-grid">
              <StatCard icon={Users} label="Total leads" value={leads.length} note="Records in database"/>
              <StatCard icon={CheckCircle2} label="Qualified leads" value={qualified} note="Marked Qualified"/>
              <StatCard icon={Target} label="Potential leads" value={potential} note="Need further evaluation"/>
              <StatCard icon={CalendarDays} label="Meetings scheduled" value={meetings} note="Lead status"/>
            </section>

            <section className="leads-panel">
              <div className="panel-header"><div><h2>{page === "Dashboard" ? "Recent leads" : "All leads"}</h2><p>Search prospects and review qualification status.</p></div>
                <label className="search-box"><Search size={17}/><input placeholder="Search leads..." value={search} onChange={(e) => setSearch(e.target.value)}/></label>
              </div>
              <div className="table-wrap"><table><thead><tr>
                <th>PROSPECT</th><th>INDUSTRY</th><th>LOCATION</th><th>ICP SCORE</th><th>QUALIFICATION</th><th>STATUS</th><th>ACTIONS</th>
              </tr></thead><tbody>
                {filteredLeads.map((lead) => <tr key={lead.id}>
                  <td><div className="prospect"><div className="avatar">{(lead.name || "?")[0].toUpperCase()}</div><div><strong>{lead.name}</strong><span>{lead.company_name}</span></div></div></td>
                  <td>{lead.industry || "—"}</td><td>{lead.location || "—"}</td>
                  <td><div className="score"><div className="score-track"><div style={{width:`${Math.min(100,Math.max(0,Number(lead.icp_score)||0))}%`}}/></div>{lead.icp_score ?? 0}</div></td>
                  <td><span className={`badge ${(lead.category||"").toLowerCase().replaceAll(" ","-")}`}>{lead.category || "Unclassified"}</span></td>
                  <td><span className="status-text">{lead.status || "New"}</span></td>
                  <td><button className="text-button" disabled={busyLead === lead.id} onClick={() => qualifyLead(lead.id)}>{busyLead === lead.id ? "Qualifying..." : "Qualify"}</button></td>
                </tr>)}
              </tbody></table>{!filteredLeads.length && <div className="empty-state">No matching leads found.</div>}</div>
              <div className="table-footer"><span>Showing {filteredLeads.length} of {leads.length} leads</span><button className="text-button" onClick={loadLeads}>Reload leads</button></div>
            </section>
          </>
        ) : (
          <section className="workflow-panel">
            <div className="panel-header"><div><h2>{page}</h2><p>Choose a lead to use the connected backend workflow.</p></div></div>
            <div className="workflow-content">
              <label className="field-label">Select lead
                <select value={selectedLead} onChange={(e) => {setSelectedLead(e.target.value);setPreview("");setChatMessages([]);setMeetingResult(null);}}>
                  {leads.map((l) => <option key={l.id} value={l.id}>{l.name} — {l.company_name}</option>)}
                </select>
              </label>
              {selected && <div className="selected-lead"><strong>{selected.name}</strong><span>{selected.company_name} · {selected.category || "Unclassified"}</span></div>}

              {page === "AI Conversations" && <>
                <div className="section-heading"><MessageSquare size={18}/> Conversation</div>
                <button className="secondary-action" onClick={loadChat} disabled={busy}>Load saved history</button>
                <div className="chat-history">
                  {chatMessages.map((m,i) => <div key={m.id || i} className={`chat-bubble ${m.role === "user" ? "user" : "assistant"}`}><span>{m.role === "user" ? "You" : "AI assistant"}</span><p>{m.message}</p></div>)}
                  {!chatMessages.length && <p className="muted">Load conversation history or send a message to begin.</p>}
                </div>
                <form className="inline-form" onSubmit={sendChat}><textarea value={chatInput} onChange={(e)=>setChatInput(e.target.value)} placeholder="Write a message..." required/><button className="primary-action" disabled={busy || !chatInput.trim()}>{busy ? "Sending..." : "Send message"}</button></form>
              </>}

              {page === "Outreach" && <>
                <div className="section-heading"><Send size={18}/> Telegram outreach</div>
                <div className="action-buttons">
                  <button className="secondary-action" onClick={previewOutreach} disabled={busy}><Eye size={16}/>Generate preview</button>
                  <button className="secondary-action" onClick={loadOutreach} disabled={busy}>Load history</button>
                </div>
                <label className="field-label">Message<textarea value={outreachMessage} onChange={(e)=>setOutreachMessage(e.target.value)} placeholder="Generate a preview or write your outreach message..." rows={7}/></label>
                <div className="action-buttons">
                  <button className="secondary-action" onClick={saveOutreach} disabled={busy || !outreachMessage.trim()}>Save draft</button>
                  <button className="primary-action" onClick={sendTelegram} disabled={busy}>Send Telegram</button>
                </div>
                <div className="section-heading"><Clock size={18}/> Outreach history</div>
                {outreachHistory.map((item)=><div className="history-item" key={item.id}><div><strong>#{item.id} · {item.channel}</strong><span>{item.status} · {item.created_at ? new Date(item.created_at).toLocaleString() : ""}</span></div><p>{item.message}</p></div>)}
                {!outreachHistory.length && <p className="muted">Load history to see saved outreach records.</p>}
              </>}

              {page === "Meetings" && <>
                <div className="section-heading"><CalendarDays size={18}/> Book a meeting</div>
                <button className="secondary-action" onClick={loadSlots} disabled={busy}><Clock size={16}/>Load available slots</button>
                <form className="meeting-form" onSubmit={bookMeeting}>
                  <label className="field-label">Meeting title<input value={meetingTitle} onChange={(e)=>setMeetingTitle(e.target.value)} required/></label>
                  <label className="field-label">Available time
                    <select value={meetingTime} onChange={(e)=>setMeetingTime(e.target.value)} required>
                      <option value="">Select a slot</option>
                      {slots.map((slot,i)=>{
                        const value = typeof slot === "string" ? slot : slot.meeting_time || slot.start_time || slot.start || slot.datetime || "";
                        return value ? <option key={`${value}-${i}`} value={value}>{new Date(value).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Kolkata"})}</option> : null;
                      })}
                    </select>
                  </label>
                  <label className="field-label">Duration<select value={meetingDuration} onChange={(e)=>setMeetingDuration(e.target.value)}><option value="30">30 minutes</option><option value="45">45 minutes</option><option value="60">60 minutes</option></select></label>
                  <label className="field-label">Notes<textarea value={meetingNotes} onChange={(e)=>setMeetingNotes(e.target.value)} placeholder="Optional meeting notes" rows={3}/></label>
                  <button className="primary-action" disabled={busy || !meetingTime}>{busy ? "Booking..." : "Book meeting"}</button>
                </form>
                {meetingResult && <div className="meeting-result"><CheckCircle2 size={20}/><div><strong>Meeting {meetingResult.status || "booked"}</strong><p>{meetingResult.meeting_title}</p><p>{meetingResult.meeting_time ? new Date(meetingResult.meeting_time).toLocaleString() : ""}</p>{meetingResult.meeting_link && <a href={meetingResult.meeting_link} target="_blank" rel="noreferrer">Open meeting link</a>}</div></div>}
                {!slots.length && <p className="muted">Load available slots before booking. Only returned slots are shown here.</p>}
              </>}
            </div>
          </section>
        )}
        <footer>LeadPilot · AI Lead Generation &amp; Client Outreach Automation</footer>
      </main>
    </div>
  );
}

function StatCard({icon: Icon,label,value,note}) {
  return <div className="stat-card"><div className="stat-top"><span>{label}</span><div className="stat-icon"><Icon size={19}/></div></div><div className="stat-value">{value}</div><div className="stat-note"><TrendingUp size={14}/>{note}</div></div>;
}

export default App;