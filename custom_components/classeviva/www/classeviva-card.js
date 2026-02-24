/**
 * ClasseViva Lovelace Card
 *
 * Displays a student's grades, noticeboard notices, upcoming agenda events
 * and downloadable didactic materials in a single Home Assistant dashboard card.
 *
 * Configuration example (Lovelace YAML):
 *
 *   type: custom:classeviva-card
 *   title: "Mario Rossi – ClasseViva"
 *   grades_entity: sensor.average_grade
 *   noticeboard_entity: sensor.noticeboard_notices
 *   agenda_entity: sensor.next_agenda_event
 *   didactics_entity: sensor.didactics_items
 *
 * After adding the resource URL /classeviva_card/classeviva-card.js in the
 * Lovelace resource settings, the card becomes available as
 * `custom:classeviva-card`.
 */

class ClasseVivaCard extends HTMLElement {
  // ------------------------------------------------------------------ //
  // LitElement-like lifecycle                                            //
  // ------------------------------------------------------------------ //

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    if (
      !config.grades_entity &&
      !config.noticeboard_entity &&
      !config.agenda_entity &&
      !config.didactics_entity
    ) {
      throw new Error(
        "classeviva-card: at least one entity must be configured " +
          "(grades_entity, noticeboard_entity, agenda_entity or didactics_entity)"
      );
    }
    this._config = config;
  }

  getCardSize() {
    return 6;
  }

  // ------------------------------------------------------------------ //
  // Helpers                                                              //
  // ------------------------------------------------------------------ //

  _state(entityId) {
    if (!entityId || !this._hass) return null;
    return this._hass.states[entityId] || null;
  }

  _attrs(entityId) {
    const s = this._state(entityId);
    return s ? s.attributes : {};
  }

  _fmt(val) {
    return val != null ? String(val) : "—";
  }

  _fmtDate(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch (_) {
      return iso;
    }
  }

  _fmtDatetime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString(undefined, {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return iso;
    }
  }

  // ------------------------------------------------------------------ //
  // Section renderers                                                    //
  // ------------------------------------------------------------------ //

  _renderGrades() {
    const attrs = this._attrs(this._config.grades_entity);
    const state = this._state(this._config.grades_entity);
    const recent = attrs.recent_grades || [];

    const rows = recent
      .map(
        (g) => `
        <tr>
          <td>${this._fmtDate(g.date)}</td>
          <td>${this._fmt(g.subject)}</td>
          <td class="grade-value">${this._fmt(g.value)}</td>
          <td class="grade-notes">${g.notes || ""}</td>
        </tr>`
      )
      .join("");

    return `
      <section>
        <h3 class="section-title">
          <span class="icon">📊</span> Voti
          <span class="badge">${state ? state.state : "—"} media</span>
        </h3>
        ${
          rows
            ? `<table class="cv-table">
                <thead><tr><th>Data</th><th>Materia</th><th>Voto</th><th>Note</th></tr></thead>
                <tbody>${rows}</tbody>
               </table>`
            : '<p class="empty">Nessun voto disponibile.</p>'
        }
      </section>`;
  }

  _renderNoticeboard() {
    const attrs = this._attrs(this._config.noticeboard_entity);
    const state = this._state(this._config.noticeboard_entity);
    const notices = attrs.notices || [];
    const unread = attrs.unread_count || 0;

    const rows = notices
      .slice(0, 10)
      .map(
        (n) => `
        <tr class="${n.read ? "" : "unread"}">
          <td>${this._fmtDate(n.begin)}</td>
          <td>${this._fmt(n.title)}${n.has_attachment ? " 📎" : ""}</td>
          <td>${this._fmt(n.author)}</td>
        </tr>`
      )
      .join("");

    return `
      <section>
        <h3 class="section-title">
          <span class="icon">📋</span> Bacheca
          ${unread > 0 ? `<span class="badge badge-warn">${unread} non letti</span>` : ""}
          <span class="badge">${state ? state.state : "—"} avvisi</span>
        </h3>
        ${
          rows
            ? `<table class="cv-table">
                <thead><tr><th>Data</th><th>Titolo</th><th>Autore</th></tr></thead>
                <tbody>${rows}</tbody>
               </table>`
            : '<p class="empty">Nessun avviso in bacheca.</p>'
        }
      </section>`;
  }

  _renderAgenda() {
    const attrs = this._attrs(this._config.agenda_entity);
    const upcoming = attrs.upcoming_events || [];

    const rows = upcoming
      .map((e) => {
        const highlight = e.student_relevant ? ' class="student-relevant"' : "";
        return `
        <tr${highlight}>
          <td>${this._fmtDatetime(e.begin)}</td>
          <td>${this._fmt(e.subject)}</td>
          <td>${this._fmt(e.notes || e.subject)}</td>
          <td>${this._fmt(e.author)}</td>
        </tr>`;
      })
      .join("");

    return `
      <section>
        <h3 class="section-title">
          <span class="icon">📅</span> Agenda
        </h3>
        ${
          rows
            ? `<table class="cv-table">
                <thead><tr><th>Quando</th><th>Materia</th><th>Note</th><th>Prof.</th></tr></thead>
                <tbody>${rows}</tbody>
               </table>
               <p class="legend" role="note">Sfondo arancione = evento personalmente rilevante per lo studente</p>`
            : '<p class="empty">Nessun evento in agenda.</p>'
        }
      </section>`;
  }

  _renderDidactics() {
    const attrs = this._attrs(this._config.didactics_entity);
    const state = this._state(this._config.didactics_entity);
    const items = attrs.items || [];

    const rows = items
      .map((it) => {
        const link = it.local_url
          ? `<a href="${it.local_url}" target="_blank" download>⬇ Scarica</a>`
          : '<span class="no-file">—</span>';
        return `
        <tr>
          <td>${this._fmt(it.teacher)}</td>
          <td>${this._fmt(it.folder)}</td>
          <td>${this._fmt(it.name)}</td>
          <td>${this._fmtDate(it.share_date)}</td>
          <td>${link}</td>
        </tr>`;
      })
      .join("");

    return `
      <section>
        <h3 class="section-title">
          <span class="icon">📚</span> Materiale didattico
          <span class="badge">${state ? state.state : "—"} elementi</span>
        </h3>
        ${
          rows
            ? `<table class="cv-table">
                <thead>
                  <tr><th>Prof.</th><th>Cartella</th><th>Titolo</th><th>Data</th><th></th></tr>
                </thead>
                <tbody>${rows}</tbody>
               </table>`
            : '<p class="empty">Nessun materiale didattico disponibile.</p>'
        }
      </section>`;
  }

  // ------------------------------------------------------------------ //
  // Main render                                                          //
  // ------------------------------------------------------------------ //

  _render() {
    if (!this._config || !this._hass) return;

    const title = this._config.title || "ClasseViva";
    const sections = [];

    if (this._config.grades_entity) sections.push(this._renderGrades());
    if (this._config.noticeboard_entity) sections.push(this._renderNoticeboard());
    if (this._config.agenda_entity) sections.push(this._renderAgenda());
    if (this._config.didactics_entity) sections.push(this._renderDidactics());

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .card-title {
          font-size: 1.2em;
          font-weight: bold;
          margin-bottom: 12px;
          color: var(--primary-text-color);
        }
        section { margin-bottom: 20px; }
        .section-title {
          font-size: 1em;
          font-weight: 600;
          margin: 0 0 8px;
          display: flex;
          align-items: center;
          gap: 6px;
          color: var(--primary-text-color);
        }
        .icon { font-size: 1.1em; }
        .badge {
          margin-left: auto;
          background: var(--primary-color, #03a9f4);
          color: #fff;
          border-radius: 12px;
          padding: 2px 8px;
          font-size: 0.75em;
          font-weight: normal;
        }
        .badge-warn {
          background: var(--warning-color, #ff9800);
        }
        .cv-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 0.85em;
        }
        .cv-table th {
          text-align: left;
          padding: 4px 6px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          color: var(--secondary-text-color);
          font-weight: 600;
        }
        .cv-table td {
          padding: 4px 6px;
          border-bottom: 1px solid var(--divider-color, #e0e0e0);
          vertical-align: top;
          color: var(--primary-text-color);
        }
        .cv-table tr:last-child td { border-bottom: none; }
        .cv-table tr.unread td { font-weight: bold; }
        .cv-table tr.student-relevant td {
          background: rgba(255, 152, 0, 0.12);
          border-left: 3px solid var(--warning-color, #ff9800);
        }
        .grade-value {
          font-weight: bold;
          color: var(--primary-color, #03a9f4);
        }
        .grade-notes { color: var(--secondary-text-color); font-style: italic; }
        a { color: var(--primary-color, #03a9f4); text-decoration: none; }
        a:hover { text-decoration: underline; }
        .no-file { color: var(--disabled-color, #bdbdbd); }
        .empty { color: var(--secondary-text-color); font-style: italic; font-size: 0.9em; }
        .legend { font-size: 0.75em; color: var(--secondary-text-color); margin-top: 4px; }
      </style>
      <ha-card>
        <div class="card-title">${title}</div>
        ${sections.join('<hr style="border:none;border-top:1px solid var(--divider-color,#e0e0e0);margin:0 0 16px">')}
      </ha-card>`;
  }
}

customElements.define("classeviva-card", ClasseVivaCard);
