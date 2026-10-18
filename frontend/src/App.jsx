import "./App.css";
import { useCallback, useEffect, useState } from "react";
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  Send,
  CalendarDays,
  RefreshCw,
  Search,
  CheckCircle2,
  Target,
  TrendingUp,
  AlertCircle,
  Sparkles,
  Clock,
  Eye,
  X,
  ExternalLink,
} from "lucide-react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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

function display(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value);
}

/**
 * Identifies discovery records that need manual verification.
 * Uses the source field where available and known discovery patterns
 * as a fallback for existing records.
 *
 * Important: this is a heuristic, not proof of identity or verification.
 * The backend should enforce verification before sending outreach.
 */
function isUnverifiedCandidate(lead) {
  if (!lead) return false;

  const source = String(lead.source || "")
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");

  const text = [
    lead.name,
    lead.company_name,
    lead.industry,
    lead.location,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return (
    source.includes("hacker_news") ||
    source.includes("hackernews") ||
    text.includes("contact not identified") ||
    text.includes("newsletter about ai") ||
    text.includes("ai roast your startup") ||
    text.includes("show hn:") ||
    text.includes("hacker news")
  );
}

/**
 * Basic frontend outreach safeguard.
 * This does not independently verify a person's identity or consent.
 */
function canContactLead(lead) {
  if (!lead) return false;

  if (isUnverifiedCandidate(lead)) {
    return false;
  }

  const name = String(lead.name || "").trim();
  const company = String(lead.company_name || "").trim();

  if (
    !name ||
    !company ||
    name.toLowerCase() === "contact not identified" ||
    company.toLowerCase() === "company not identified" ||
    name.toLowerCase() === "unknown prospect" ||
    company.toLowerCase() === "unknown company"
  ) {
    return false;
  }

  return true;
}

function qualificationClass(category) {
  return (category || "unclassified")
    .toLowerCase()
    .replaceAll(" ", "-");
}

function App() {
  const [leads, setLeads] = useState([]);
  const [meetingCount, setMeetingCount] = useState(0);
  const [page, setPage] = useState("Dashboard");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [busyLead, setBusyLead] = useState(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [qualificationResult, setQualificationResult] = useState(null);

  const [selectedLead, setSelectedLead] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState([]);

  const [preview, setPreview] = useState("");
  const [outreachMessage, setOutreachMessage] = useState("");
  const [outreachHistory, setOutreachHistory] = useState([]);

  const [slots, setSlots] = useState([]);
  const [meetingTime, setMeetingTime] = useState("");
  const [meetingTitle, setMeetingTitle] = useState(
    "Lead Discovery Meeting"
  );
  const [meetingDuration, setMeetingDuration] = useState("30");
  const [meetingNotes, setMeetingNotes] = useState("");
  const [meetingResult, setMeetingResult] = useState(null);

  const loadMeetings = useCallback(async () => {
    const data = await api("/api/leads/meetings");

    if (!Array.isArray(data.meetings)) {
      throw new Error("Unexpected meetings response.");
    }

    setMeetingCount(
      data.meetings.filter(
        (meeting) => meeting.status === "Scheduled"
      ).length
    );
  }, []);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await api("/api/leads/");

      if (!Array.isArray(data)) {
        throw new Error("Unexpected leads response.");
      }

      setLeads(data);

      setSelectedLead((old) =>
        data.some((lead) => String(lead.id) === old)
          ? old
          : String(data[0]?.id ?? "")
      );

      try {
        await loadMeetings();
      } catch (meetingError) {
        setError(
          `Leads loaded, but meetings could not be refreshed: ${meetingError.message}`
        );
      }
    } catch (e) {
      setError(`Could not load leads: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [loadMeetings]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  const leadId = Number(selectedLead);

  const selected = leads.find(
    (lead) => Number(lead.id) === leadId
  );

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
    setBusy(true);
    setError("");
    setNotice("");

    try {
      const data = await api("/api/leads/discover", {
        method: "POST",
      });

      await loadLeads();

      setNotice(
        `Discovery complete: ${data.created_count ?? 0} new candidates added; ` +
          `${data.skipped_duplicates_or_invalid ?? 0} duplicates or invalid candidates skipped. ` +
          "Discovered candidates may need manual verification before outreach."
      );
    } catch (e) {
      setError(e.message || "Lead discovery failed.");
    } finally {
      setBusy(false);
    }
  }

  async function qualifyLead(id) {
    setBusyLead(id);
    setError("");
    setNotice("");
    setQualificationResult(null);

    try {
      const data = await api(`/api/leads/${id}/qualify`, {
        method: "POST",
      });

      const result = {
        lead_id: id,
        category: data.category || "Unclassified",
        buying_intent: data.buying_intent || "Unknown",
        pain_points:
          data.pain_points ||
          "Not established from available information",
        summary:
          data.summary ||
          data.ai_summary ||
          "No qualification summary was returned.",
      };

      setQualificationResult(result);
      setNotice(`Lead #${id} qualified: ${result.category}.`);

      const refreshed = await api("/api/leads/");

      if (Array.isArray(refreshed)) {
        setLeads(refreshed);
      }
    } catch (e) {
      setError(e.message || "Qualification failed.");
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
    setNotice("");

    try {
      const data = await api(`/api/leads/${leadId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });

      setChatMessages((old) => [
        ...old,
        {
          role: "user",
          message: data.user_message || message,
        },
        {
          role: "assistant",
          message: data.ai_reply || "No reply returned.",
        },
      ]);

      setChatInput("");
      setNotice("AI conversation updated.");
    } catch (e) {
      setError(e.message || "Could not send message.");
    } finally {
      setBusy(false);
    }
  }

  async function previewOutreach() {
    if (!leadId) {
      setError("Select a lead first.");
      return;
    }

    await runAction(async () => {
      const data = await api(
        `/api/leads/${leadId}/outreach/preview`,
        { method: "POST" }
      );

      const message =
        typeof data === "string"
          ? data
          : data.message ||
            data.preview ||
            data.draft ||
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

      const data = await api(`/api/leads/${leadId}/outreach`);
      setOutreachHistory(data.outreach || []);
    }, "Outreach draft saved.");
  }

  async function sendTelegram() {
    if (!leadId || !selected) {
      setError("Select a lead first.");
      return;
    }

    if (isUnverifiedCandidate(selected)) {
      setError(
        "Outreach blocked: this is an unverified discovery candidate. " +
          "Verify the person's identity, company, contact details, and permission to contact first."
      );
      return;
    }

    if (!canContactLead(selected)) {
      setError(
        "Outreach blocked: this lead is missing basic prospect details. " +
          "Verify the prospect before sending."
      );
      return;
    }

    await runAction(async () => {
      const data = await api(
        `/api/leads/${leadId}/outreach/send-telegram`,
        { method: "POST" }
      );

      const history = await api(`/api/leads/${leadId}/outreach`);
      setOutreachHistory(history.outreach || []);

      setNotice(
        `Telegram send request completed. Message ID: ${
          data.telegram_message_id ?? "not returned"
        }.`
      );
    }, "Telegram send request completed.");
  }

  async function loadOutreach() {
    if (!leadId) {
      setError("Select a lead first.");
      return;
    }

    await runAction(async () => {
      const data = await api(`/api/leads/${leadId}/outreach`);
      setOutreachHistory(data.outreach || []);
    }, "Outreach history loaded.");
  }

  async function loadSlots() {
    await runAction(async () => {
      const data = await api("/api/leads/meetings/slots");

      setSlots(
        Array.isArray(data)
          ? data
          : data.slots || data.available_slots || []
      );

      setMeetingTime("");
      setMeetingResult(null);
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
      await loadMeetings();
    }, "Meeting booking request completed.");
  }

  const filteredLeads = leads.filter((lead) =>
    [
      lead.name,
      lead.company_name,
      lead.industry,
      lead.location,
      lead.category,
      lead.status,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(search.toLowerCase())
  );

  const qualified = leads.filter(
    (lead) => lead.category === "Qualified"
  ).length;

  const potential = leads.filter(
    (lead) => lead.category === "Potential"
  ).length;

  const unverifiedCandidateCount =
    leads.filter(isUnverifiedCandidate).length;

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
          <div>
            <h2>LeadPilot</h2>
            <span>AI Outreach Platform</span>
          </div>
        </div>

        <p className="nav-label">WORKSPACE</p>

        <nav>
          {navItems.map(([name, Icon]) => (
            <button
              key={name}
              className={`nav-item ${page === name ? "active" : ""}`}
              onClick={() => {
                setPage(name);
                setError("");
                setNotice("");
              }}
            >
              <Icon size={18} />
              <span>{name}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className={`status-dot ${error ? "offline" : ""}`} />
          <div>
            <strong>Backend API</strong>
            <span>
              {error ? "Check connection" : "Connection available"}
            </span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">
              WORKSPACE / {page.toUpperCase()}
            </span>
            <h1>{page === "Dashboard" ? "Overview" : page}</h1>
          </div>

          <button
            className="refresh-button"
            onClick={loadLeads}
            disabled={loading}
          >
            <RefreshCw
              size={16}
              className={loading ? "spin" : ""}
            />
            {loading ? "Refreshing..." : "Refresh data"}
          </button>
        </header>

        {error && (
          <div className="error-banner" role="alert">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {notice && (
          <div className="success-banner" role="status">
            <CheckCircle2 size={18} />
            <span>{notice}</span>
          </div>
        )}

        {page === "Dashboard" || page === "Leads" ? (
          <>
            <section className="welcome-panel">
              <div>
                <span className="welcome-tag">
                  AI-POWERED WORKFLOW
                </span>
                <h2>Turn prospects into opportunities.</h2>
                <p>
                  Discover, qualify, contact and schedule meetings with
                  your leads.
                </p>
              </div>

              <div className="welcome-symbol">
                <Target size={42} />
              </div>
            </section>

            <section className="action-toolbar">
              <div>
                <h2>
                  <Sparkles size={17} /> Lead actions
                </h2>
                <p>
                  Discover candidate leads and run AI qualification.
                </p>
              </div>

              <div className="action-buttons">
                <button
                  className="primary-action"
                  disabled={busy}
                  onClick={discoverLeads}
                >
                  <Search size={16} />
                  {busy ? "Working..." : "Discover leads"}
                </button>

                <button
                  className="secondary-action"
                  onClick={loadLeads}
                  disabled={loading}
                >
                  <RefreshCw size={15} />
                  Refresh leads
                </button>
              </div>
            </section>

            <section className="stats-grid">
              <StatCard
                icon={Users}
                label="Total leads"
                value={leads.length}
                note="Records in database"
              />

              <StatCard
                icon={CheckCircle2}
                label="Qualified leads"
                value={qualified}
                note="AI qualification category"
              />

              <StatCard
                icon={Target}
                label="Potential leads"
                value={potential}
                note="Need further evaluation"
              />

              <StatCard
                icon={CalendarDays}
                label="Meetings scheduled"
                value={meetingCount}
                note="Records with Scheduled status"
              />
            </section>

            {qualificationResult && (
              <section className="workflow-panel qualification-panel">
                <div className="panel-header">
                  <div>
                    <h2>
                      <Sparkles size={18} /> AI Qualification Result
                    </h2>
                    <p>
                      Qualification details for lead #
                      {qualificationResult.lead_id}
                    </p>
                  </div>

                  <button
                    className="icon-button"
                    aria-label="Close qualification result"
                    onClick={() => setQualificationResult(null)}
                  >
                    <X size={18} />
                  </button>
                </div>

                <div className="workflow-content">
                  <p>
                    <strong>Category:</strong>{" "}
                    <span
                      className={`badge ${qualificationClass(
                        qualificationResult.category
                      )}`}
                    >
                      {qualificationResult.category}
                    </span>
                  </p>

                  <p>
                    <strong>Buying intent:</strong>{" "}
                    {qualificationResult.buying_intent}
                  </p>

                  <p>
                    <strong>Pain points:</strong>{" "}
                    {qualificationResult.pain_points}
                  </p>

                  <p>
                    <strong>AI summary:</strong>{" "}
                    {qualificationResult.summary}
                  </p>
                </div>
              </section>
            )}

            <section className="leads-panel">
              <div className="panel-header">
                <div>
                  <h2>
                    {page === "Dashboard" ? "Recent leads" : "All leads"}
                  </h2>
                  <p>
                    Qualification indicates fit; workflow status indicates
                    progress through the process.
                  </p>
                </div>

                <label className="search-box">
                  <Search size={17} />
                  <input
                    placeholder="Search leads..."
                    value={search}
                    onChange={(event) =>
                      setSearch(event.target.value)
                    }
                  />
                </label>
              </div>

              <div className="verification-note" role="note">
                <AlertCircle size={18} />

                <div>
                  <strong>
                    Discovery results require verification
                    {unverifiedCandidateCount > 0
                      ? ` (${unverifiedCandidateCount} identified)`
                      : ""}
                  </strong>

                  <p>
                    Lead discovery finds potentially relevant discussions
                    and public posts. These records are candidates—not
                    confirmed people, companies, or customers. Some may
                    not contain a verified contact, company name, or
                    location.
                  </p>

                  <p>
                    <strong>Before outreach:</strong> verify the person's
                    identity, company, contact details, and fit with your
                    ideal customer profile (ICP). Confirm that contacting
                    them is appropriate. Do not send messages to
                    unverified candidates.
                  </p>
                </div>
              </div>

              <div className="table-wrap">
                <table className="leads-table">
                  <thead>
                    <tr>
                      <th>PROSPECT</th>
                      <th>INDUSTRY</th>
                      <th>LOCATION</th>
                      <th>ICP SCORE</th>
                      <th>QUALIFICATION</th>
                      <th>WORKFLOW STATUS</th>
                      <th>ACTIONS</th>
                    </tr>
                  </thead>

                  <tbody>
                    {filteredLeads.map((lead) => {
                      const candidate = isUnverifiedCandidate(lead);

                      const name = display(
                        lead.name,
                        "Unknown prospect"
                      );

                      const company = display(
                        lead.company_name,
                        "Company not identified"
                      );

                      return (
                        <tr key={lead.id}>
                          <td className="prospect-cell">
                            <div className="prospect">
                              <div className="avatar">
                                {name.charAt(0).toUpperCase()}
                              </div>

                              <div className="prospect-details">
                                <strong title={name}>{name}</strong>
                                <span title={company}>{company}</span>

                                {candidate && (
                                  <span className="verification-label">
                                    <AlertCircle size={12} />
                                    Needs verification
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>

                          <td className="wrap-cell">
                            {display(lead.industry)}
                          </td>

                          <td className="wrap-cell">
                            {display(lead.location)}
                          </td>

                          <td>
                            <div className="score">
                              <div className="score-track">
                                <div
                                  style={{
                                    width: `${Math.min(
                                      100,
                                      Math.max(
                                        0,
                                        Number(lead.icp_score) || 0
                                      )
                                    )}%`,
                                  }}
                                />
                              </div>
                              <span>{lead.icp_score ?? 0}</span>
                            </div>
                          </td>

                          <td>
                            <span
                              className={`badge ${qualificationClass(
                                lead.category
                              )}`}
                            >
                              {display(
                                lead.category,
                                "Unclassified"
                              )}
                            </span>
                          </td>

                          <td>
                            <span
                              className={`status-pill ${String(
                                lead.status || "New"
                              )
                                .toLowerCase()
                                .replaceAll(" ", "-")}`}
                            >
                              {display(lead.status, "New")}
                            </span>
                          </td>

                          <td>
                            <button
                              className="text-button"
                              disabled={
                                busyLead === lead.id || busy
                              }
                              onClick={() => qualifyLead(lead.id)}
                            >
                              {busyLead === lead.id
                                ? "Qualifying..."
                                : "Qualify"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                {!filteredLeads.length && (
                  <div className="empty-state">
                    No matching leads found.
                  </div>
                )}
              </div>

              <div className="table-footer">
                <span>
                  Showing {filteredLeads.length} of {leads.length} leads
                </span>

                <button
                  className="text-button"
                  onClick={loadLeads}
                  disabled={loading}
                >
                  Reload leads
                </button>
              </div>
            </section>
          </>
        ) : (
          <section className="workflow-panel">
            <div className="panel-header">
              <div>
                <h2>{page}</h2>
                <p>
                  Choose a lead to use the connected backend workflow.
                </p>
              </div>
            </div>

            <div className="workflow-content">
              <label className="field-label">
                Select lead

                <select
                  value={selectedLead}
                  onChange={(event) => {
                    setSelectedLead(event.target.value);
                    setPreview("");
                    setOutreachMessage("");
                    setOutreachHistory([]);
                    setChatMessages([]);
                    setMeetingResult(null);
                    setMeetingTime("");
                    setError("");
                    setNotice("");
                  }}
                >
                  {leads.map((lead) => (
                    <option key={lead.id} value={lead.id}>
                      {display(lead.name, "Unknown prospect")} —{" "}
                      {display(
                        lead.company_name,
                        "Unknown company"
                      )}
                    </option>
                  ))}
                </select>
              </label>

              {selected && (
                <div className="selected-lead">
                  <strong>
                    {display(selected.name, "Unknown prospect")}
                  </strong>

                  <span>
                    {display(
                      selected.company_name,
                      "Unknown company"
                    )}{" "}
                    · {display(selected.category, "Unclassified")}
                  </span>

                  {isUnverifiedCandidate(selected) ? (
                    <p className="verification-label">
                      <AlertCircle size={14} />
                      Unverified candidate — verify before outreach
                    </p>
                  ) : (
                    <p className="verification-label">
                      <AlertCircle size={14} />
                      Verify identity, contact details, and permission
                      to contact before sending
                    </p>
                  )}
                </div>
              )}

              {page === "AI Conversations" && (
                <>
                  <div className="section-heading">
                    <MessageSquare size={18} /> Conversation
                  </div>

                  <button
                    className="secondary-action"
                    onClick={loadChat}
                    disabled={busy || !leadId}
                  >
                    Load saved history
                  </button>

                  <div className="chat-history">
                    {chatMessages.map((message, index) => (
                      <div
                        key={message.id || index}
                        className={`chat-bubble ${
                          message.role === "user"
                            ? "user"
                            : "assistant"
                        }`}
                      >
                        <span>
                          {message.role === "user"
                            ? "You"
                            : "AI assistant"}
                        </span>
                        <p>{message.message}</p>
                      </div>
                    ))}

                    {!chatMessages.length && (
                      <p className="muted">
                        Load conversation history or send a message
                        to begin.
                      </p>
                    )}
                  </div>

                  <form
                    className="inline-form"
                    onSubmit={sendChat}
                  >
                    <textarea
                      value={chatInput}
                      onChange={(event) =>
                        setChatInput(event.target.value)
                      }
                      placeholder="Write a message..."
                      required
                    />

                    <button
                      className="primary-action"
                      disabled={busy || !chatInput.trim() || !leadId}
                    >
                      {busy ? "Sending..." : "Send message"}
                    </button>
                  </form>
                </>
              )}

              {page === "Outreach" && (
                <>
                  <div className="section-heading">
                    <Send size={18} /> Telegram outreach
                  </div>

                  {selected && isUnverifiedCandidate(selected) && (
                    <div className="verification-note" role="alert">
                      <AlertCircle size={18} />
                      <div>
                        <strong>Outreach is disabled for this candidate</strong>
                        <p>
                          Verify the prospect's identity, company,
                          contact details, and appropriateness of contact
                          before attempting outreach. You can still
                          prepare and save a draft for review.
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="action-buttons">
                    <button
                      className="secondary-action"
                      onClick={previewOutreach}
                      disabled={busy || !leadId}
                    >
                      <Eye size={16} /> Generate preview
                    </button>

                    <button
                      className="secondary-action"
                      onClick={loadOutreach}
                      disabled={busy || !leadId}
                    >
                      Load history
                    </button>
                  </div>

                  <label className="field-label">
                    Message

                    <textarea
                      value={outreachMessage}
                      onChange={(event) =>
                        setOutreachMessage(event.target.value)
                      }
                      placeholder="Generate a preview or write your outreach message..."
                      rows={7}
                    />
                  </label>

                  <div className="action-buttons">
                    <button
                      className="secondary-action"
                      onClick={saveOutreach}
                      disabled={
                        busy || !leadId || !outreachMessage.trim()
                      }
                    >
                      Save draft
                    </button>

                    <button
                      className="primary-action"
                      onClick={sendTelegram}
                      disabled={
                        busy ||
                        !selected ||
                        !canContactLead(selected)
                      }
                      title={
                        selected && !canContactLead(selected)
                          ? "Verify this candidate and complete prospect details before outreach"
                          : "Send Telegram outreach"
                      }
                    >
                      <Send size={16} />
                      {selected && !canContactLead(selected)
                        ? "Verification required"
                        : "Send Telegram"}
                    </button>
                  </div>

                  <div className="section-heading">
                    <Clock size={18} /> Outreach history
                  </div>

                  {outreachHistory.map((item) => (
                    <div className="history-item" key={item.id}>
                      <div>
                        <strong>
                          #{item.id} · {item.channel}
                        </strong>

                        <span>
                          {item.status} ·{" "}
                          {item.created_at
                            ? new Date(
                                item.created_at
                              ).toLocaleString()
                            : ""}
                        </span>
                      </div>

                      <p>{item.message}</p>
                    </div>
                  ))}

                  {!outreachHistory.length && (
                    <p className="muted">
                      Load history to see saved outreach records.
                    </p>
                  )}
                </>
              )}

              {page === "Meetings" && (
                <>
                  <div className="section-heading">
                    <CalendarDays size={18} /> Book a meeting
                  </div>

                  <button
                    className="secondary-action"
                    onClick={loadSlots}
                    disabled={busy}
                  >
                    <Clock size={16} /> Load available slots
                  </button>

                  <form
                    className="meeting-form"
                    onSubmit={bookMeeting}
                  >
                    <label className="field-label">
                      Meeting title

                      <input
                        value={meetingTitle}
                        onChange={(event) =>
                          setMeetingTitle(event.target.value)
                        }
                        required
                      />
                    </label>

                    <label className="field-label">
                      Available time

                      <select
                        value={meetingTime}
                        onChange={(event) =>
                          setMeetingTime(event.target.value)
                        }
                        required
                      >
                        <option value="">Select a slot</option>

                        {slots.map((slot, index) => {
                          const value =
                            typeof slot === "string"
                              ? slot
                              : slot.meeting_time ||
                                slot.start_time ||
                                slot.start ||
                                slot.datetime ||
                                "";

                          return value ? (
                            <option
                              key={`${value}-${index}`}
                              value={value}
                            >
                              {new Date(value).toLocaleString(
                                "en-IN",
                                {
                                  dateStyle: "medium",
                                  timeStyle: "short",
                                  timeZone: "Asia/Kolkata",
                                }
                              )}
                            </option>
                          ) : null;
                        })}
                      </select>
                    </label>

                    <label className="field-label">
                      Duration

                      <select
                        value={meetingDuration}
                        onChange={(event) =>
                          setMeetingDuration(event.target.value)
                        }
                      >
                        <option value="30">30 minutes</option>
                        <option value="45">45 minutes</option>
                        <option value="60">60 minutes</option>
                      </select>
                    </label>

                    <label className="field-label">
                      Notes

                      <textarea
                        value={meetingNotes}
                        onChange={(event) =>
                          setMeetingNotes(event.target.value)
                        }
                        placeholder="Optional meeting notes"
                        rows={3}
                      />
                    </label>

                    <button
                      className="primary-action"
                      disabled={busy || !meetingTime || !leadId}
                    >
                      {busy ? "Booking..." : "Book meeting"}
                    </button>
                  </form>

                  {meetingResult && (
                    <div className="meeting-result">
                      <CheckCircle2 size={20} />

                      <div>
                        <strong>
                          Meeting {meetingResult.status || "booking requested"}
                        </strong>

                        <p>{meetingResult.meeting_title}</p>

                        <p>
                          {meetingResult.meeting_time
                            ? new Date(
                                meetingResult.meeting_time
                              ).toLocaleString("en-IN", {
                                timeZone: "Asia/Kolkata",
                              })
                            : ""}
                        </p>

                        {meetingResult.meeting_link && (
                          <a
                            href={meetingResult.meeting_link}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open meeting link{" "}
                            <ExternalLink size={13} />
                          </a>
                        )}
                      </div>
                    </div>
                  )}

                  {!slots.length && (
                    <p className="muted">
                      Load available slots before booking. Only returned
                      slots are shown here.
                    </p>
                  )}
                </>
              )}
            </div>
          </section>
        )}

        <footer>
          LeadPilot · AI Lead Generation &amp; Client Outreach Automation
        </footer>
      </main>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, note }) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{label}</span>
        <div className="stat-icon">
          <Icon size={19} />
        </div>
      </div>

      <div className="stat-value">{value}</div>

      <div className="stat-note">
        <TrendingUp size={14} /> {note}
      </div>
    </div>
  );
}

export default App;