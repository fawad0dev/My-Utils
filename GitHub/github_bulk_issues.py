import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import csv
import threading
import requests
import time
import os

# ─────────────────────────────────────────────
#  GitHub API Helper
# ─────────────────────────────────────────────
class GitHubAPI:
    BASE = "https://api.github.com"

    def __init__(self, token):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        })

    def get_user(self):
        return self.session.get(f"{self.BASE}/user")

    def get_repos(self):
        repos, page = [], 1
        while True:
            r = self.session.get(f"{self.BASE}/user/repos",
                                 params={"per_page": 100, "page": page, "affiliation": "owner,collaborator,organization_member"})
            data = r.json()
            if not data or not isinstance(data, list):
                break
            repos.extend(data)
            if len(data) < 100:
                break
            page += 1
        return repos

    def get_labels(self, owner, repo):
        r = self.session.get(f"{self.BASE}/repos/{owner}/{repo}/labels", params={"per_page": 100})
        return r.json() if r.ok else []

    def get_milestones(self, owner, repo):
        r = self.session.get(f"{self.BASE}/repos/{owner}/{repo}/milestones", params={"per_page": 100})
        return r.json() if r.ok else []

    def get_assignees(self, owner, repo):
        r = self.session.get(f"{self.BASE}/repos/{owner}/{repo}/assignees", params={"per_page": 100})
        return r.json() if r.ok else []

    def create_issue(self, owner, repo, payload):
        return self.session.post(f"{self.BASE}/repos/{owner}/{repo}/issues", json=payload)


# ─────────────────────────────────────────────
#  Main App
# ─────────────────────────────────────────────
class BulkIssueApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GitHub Bulk Issue Creator")
        self.geometry("1000x780")
        self.configure(bg="#0d1117")
        self.resizable(True, True)

        self.api: GitHubAPI | None = None
        self.issues_data: list[dict] = []
        self.labels_cache: list[str] = []
        self.milestone_map: dict = {}
        self.assignees_cache: list[str] = []

        self._style()
        self._build_ui()

    # ── Styles ──────────────────────────────
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        bg, fg, accent = "#0d1117", "#c9d1d9", "#238636"
        entry_bg = "#161b22"
        s.configure(".", background=bg, foreground=fg, font=("Segoe UI", 10))
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("TButton", background=accent, foreground="#fff", padding=6, relief="flat")
        s.map("TButton", background=[("active", "#2ea043")])
        s.configure("Danger.TButton", background="#da3633", foreground="#fff", padding=6, relief="flat")
        s.map("Danger.TButton", background=[("active", "#b91c1c")])
        s.configure("TEntry", fieldbackground=entry_bg, foreground=fg, insertcolor=fg)
        s.configure("TCombobox", fieldbackground=entry_bg, foreground=fg, selectbackground=entry_bg)
        s.configure("Treeview", background=entry_bg, foreground=fg,
                    fieldbackground=entry_bg, rowheight=28)
        s.configure("Treeview.Heading", background="#21262d", foreground=fg, relief="flat")
        s.configure("TNotebook", background=bg, tabmargins=[2, 5, 2, 0])
        s.configure("TNotebook.Tab", background="#21262d", foreground=fg, padding=[12, 5])
        s.map("TNotebook.Tab", background=[("selected", accent)])
        s.configure("TLabelframe", background=bg, foreground=fg)
        s.configure("TLabelframe.Label", background=bg, foreground="#58a6ff")
        s.configure("TCheckbutton", background=bg, foreground=fg)
        s.configure("TProgressbar", troughcolor="#21262d", background=accent)

    # ── Build UI ────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg="#161b22", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚡ GitHub Bulk Issue Creator",
                 font=("Segoe UI", 16, "bold"), bg="#161b22", fg="#58a6ff").pack(side="left", padx=20)
        self.status_lbl = tk.Label(hdr, text="● Not connected", fg="#da3633",
                                   bg="#161b22", font=("Segoe UI", 10))
        self.status_lbl.pack(side="right", padx=20)

        # Notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._tab_connect()
        self._tab_single()
        self._tab_bulk()
        self._tab_smart_paste()
        self._tab_template()
        self._tab_log()

    # ── Tab 1: Connect ───────────────────────
    def _tab_connect(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="🔑  Connect")

        card = ttk.LabelFrame(f, text="GitHub Authentication", padding=20)
        card.pack(padx=30, pady=30, fill="x")

        ttk.Label(card, text="Personal Access Token (classic or fine-grained):").grid(row=0, column=0, sticky="w", pady=4)
        self.token_var = tk.StringVar()
        te = ttk.Entry(card, textvariable=self.token_var, width=60, show="*")
        te.grid(row=0, column=1, padx=10, sticky="ew")
        ttk.Button(card, text="👁 Show/Hide",
                   command=lambda: te.config(show="" if te.cget("show") == "*" else "*")).grid(row=0, column=2)

        ttk.Label(card, text="Repository (owner/repo):").grid(row=1, column=0, sticky="w", pady=4)
        self.repo_var = tk.StringVar()
        self.repo_combo = ttk.Combobox(card, textvariable=self.repo_var, width=58)
        self.repo_combo.grid(row=1, column=1, padx=10, sticky="ew")
        ttk.Button(card, text="🔃 Load Repos",
                   command=self._load_repos).grid(row=1, column=2)

        ttk.Button(card, text="✅  Connect & Verify",
                   command=self._connect).grid(row=2, column=1, pady=14, sticky="w", padx=10)

        card.columnconfigure(1, weight=1)

        # Info card
        info = ttk.LabelFrame(f, text="Required Token Scopes", padding=15)
        info.pack(padx=30, pady=0, fill="x")
        scopes = [
            ("repo", "Full control of private repositories"),
            ("read:org", "Read org membership (for org repos)"),
        ]
        for i, (scope, desc) in enumerate(scopes):
            tk.Label(info, text=f"  ✔  {scope}", fg="#3fb950", bg="#0d1117",
                     font=("Segoe UI", 10, "bold")).grid(row=i, column=0, sticky="w")
            ttk.Label(info, text=f"— {desc}").grid(row=i, column=1, sticky="w", padx=10)

    # ── Tab 2: Single Issue ──────────────────
    def _tab_single(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="📝  Single Issue")

        card = ttk.LabelFrame(f, text="Create One Issue", padding=15)
        card.pack(padx=20, pady=20, fill="both", expand=True)

        fields = [
            ("Title *", "s_title"),
            ("Labels (comma-separated)", "s_labels"),
            ("Assignees (comma-separated)", "s_assignees"),
            ("Milestone", "s_milestone"),
        ]
        self.single_vars = {}
        for i, (lbl, key) in enumerate(fields):
            ttk.Label(card, text=lbl).grid(row=i, column=0, sticky="w", pady=5, padx=5)
            if key == "s_milestone":
                self.s_milestone_combo = ttk.Combobox(card, width=50)
                self.s_milestone_combo.grid(row=i, column=1, sticky="ew", padx=5)
            else:
                var = tk.StringVar()
                self.single_vars[key] = var
                ttk.Entry(card, textvariable=var, width=52).grid(row=i, column=1, sticky="ew", padx=5)

        ttk.Label(card, text="Body (Markdown supported)").grid(row=len(fields), column=0, sticky="nw", pady=5, padx=5)
        self.s_body = scrolledtext.ScrolledText(card, height=8, bg="#161b22", fg="#c9d1d9",
                                                insertbackground="#c9d1d9", relief="flat", font=("Consolas", 10))
        self.s_body.grid(row=len(fields), column=1, sticky="nsew", padx=5, pady=5)

        # Options row
        opt = ttk.Frame(card)
        opt.grid(row=len(fields)+1, column=0, columnspan=2, sticky="w", pady=8)
        self.s_dry = tk.BooleanVar()
        ttk.Checkbutton(opt, text="Dry Run (preview only)", variable=self.s_dry).pack(side="left", padx=10)

        ttk.Button(card, text="🚀  Create Issue",
                   command=self._create_single).grid(row=len(fields)+2, column=1, sticky="e", padx=5, pady=5)

        card.columnconfigure(1, weight=1)
        card.rowconfigure(len(fields), weight=1)

    # ── Tab 3: Bulk CSV/JSON ─────────────────
    def _tab_bulk(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="📦  Bulk Import")

        top = ttk.LabelFrame(f, text="Import Issues from CSV or JSON", padding=15)
        top.pack(padx=20, pady=15, fill="x")

        btn_row = ttk.Frame(top)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="📂  Load CSV", command=self._load_csv).pack(side="left", padx=5)
        ttk.Button(btn_row, text="📂  Load JSON", command=self._load_json).pack(side="left", padx=5)
        ttk.Button(btn_row, text="💾  Download CSV Template",
                   command=self._download_csv_template).pack(side="left", padx=5)
        ttk.Button(btn_row, text="💾  Download JSON Template",
                   command=self._download_json_template).pack(side="left", padx=5)
        ttk.Button(btn_row, text="🗑  Clear All", style="Danger.TButton",
                   command=self._clear_issues).pack(side="right", padx=5)

        # Delay control
        delay_row = ttk.Frame(top)
        delay_row.pack(fill="x", pady=(10, 0))
        ttk.Label(delay_row, text="Delay between requests (seconds):").pack(side="left", padx=5)
        self.delay_var = tk.DoubleVar(value=0.5)
        ttk.Spinbox(delay_row, from_=0.1, to=5.0, increment=0.1,
                    textvariable=self.delay_var, width=8).pack(side="left")
        self.dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(delay_row, text="Dry Run (preview only — no API calls)",
                        variable=self.dry_run_var).pack(side="left", padx=20)

        # Preview table
        tbl_frame = ttk.LabelFrame(f, text="Preview Issues", padding=5)
        tbl_frame.pack(padx=20, pady=5, fill="both", expand=True)

        cols = ("title", "body", "labels", "assignees", "milestone")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=12)
        widths = {"title": 220, "body": 260, "labels": 140, "assignees": 120, "milestone": 110}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        vsb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Right-click menu
        self.ctx_menu = tk.Menu(self, tearoff=0, bg="#21262d", fg="#c9d1d9")
        self.ctx_menu.add_command(label="Delete selected row", command=self._delete_row)
        self.tree.bind("<Button-3>", self._show_ctx)

        # Progress
        prog_frame = ttk.Frame(f)
        prog_frame.pack(padx=20, pady=5, fill="x")
        self.progress = ttk.Progressbar(prog_frame, mode="determinate")
        self.progress.pack(fill="x", side="left", expand=True, padx=(0, 10))
        self.prog_lbl = ttk.Label(prog_frame, text="0 / 0")
        self.prog_lbl.pack(side="left")

        btn2 = ttk.Frame(f)
        btn2.pack(padx=20, pady=8, fill="x")
        self.issues_count_lbl = ttk.Label(btn2, text="No issues loaded")
        self.issues_count_lbl.pack(side="left")
        ttk.Button(btn2, text="🚀  Create All Issues",
                   command=self._bulk_create).pack(side="right")

    # ── Tab 4: Smart Paste ───────────────────
    def _tab_smart_paste(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="📌  Smart Paste")

        info = ttk.LabelFrame(f, text="Paste Raw Text → Auto-Generate Issues", padding=15)
        info.pack(padx=20, pady=15, fill="x")
        ttk.Label(info, text="Paste any format below:").pack(anchor="w")
        ttk.Label(info, text="✓ Bullet points  |  ✓ Numbered lists  |  ✓ Plain lines  |  ✓ Mixed",
                  foreground="#58a6ff").pack(anchor="w", pady=5)

        card = ttk.LabelFrame(f, text="Paste Lines Here", padding=15)
        card.pack(padx=20, pady=10, fill="both", expand=True)

        self.paste_text = scrolledtext.ScrolledText(card, height=12, bg="#161b22", fg="#c9d1d9",
                                                    insertbackground="#c9d1d9", relief="flat",
                                                    font=("Consolas", 10))
        self.paste_text.pack(fill="both", expand=True)

        # Options
        opts = ttk.LabelFrame(f, text="Settings", padding=12)
        opts.pack(padx=20, pady=8, fill="x")

        opt_row1 = ttk.Frame(opts)
        opt_row1.pack(fill="x", pady=5)
        ttk.Label(opt_row1, text="Prefix:").pack(side="left", padx=5)
        self.smart_prefix = tk.StringVar(value="[TASK]")
        ttk.Entry(opt_row1, textvariable=self.smart_prefix, width=15).pack(side="left", padx=5)

        ttk.Label(opt_row1, text="Type:").pack(side="left", padx=20)
        self.smart_type = tk.StringVar(value="auto")
        ttk.Combobox(opt_row1, textvariable=self.smart_type, width=15,
                     values=["auto", "bug", "enhancement", "feature", "chore"]).pack(side="left", padx=5)

        opt_row2 = ttk.Frame(opts)
        opt_row2.pack(fill="x", pady=5)
        ttk.Label(opt_row2, text="Default Labels (comma-separated):").pack(side="left", padx=5)
        self.smart_labels = tk.StringVar()
        ttk.Entry(opt_row2, textvariable=self.smart_labels, width=30).pack(side="left", padx=5)

        ttk.Label(opt_row2, text="Assignee:").pack(side="left", padx=20)
        self.smart_assignee = tk.StringVar(value="fawad0dev")
        ttk.Entry(opt_row2, textvariable=self.smart_assignee, width=15).pack(side="left", padx=5)

        # Actions
        btn_row = ttk.Frame(f)
        btn_row.pack(padx=20, pady=8, fill="x")
        ttk.Button(btn_row, text="🧹 Clear", command=self._clear_paste).pack(side="left", padx=5)
        ttk.Button(btn_row, text="✨ Auto-Convert to Issues",
                   command=self._smart_parse).pack(side="left", padx=5)
        ttk.Button(btn_row, text="👁 Preview",
                   command=self._preview_parsed).pack(side="left", padx=5)

    def _clear_paste(self):
        self.paste_text.delete("1.0", "end")

    def _smart_parse(self):
        raw = self.paste_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showerror("Empty", "Paste some lines first.")
            return

        lines = raw.splitlines()
        parsed = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove common prefixes
            for prefix in ["-", "•", "◦", "*", "+", "—", "–"]:
                if line.startswith(prefix):
                    line = line[1:].strip()
                    break

            # Remove numbering
            import re
            line = re.sub(r"^\d+[\.\)]\s*", "", line)

            if len(line) < 3:
                continue

            # Determine type
            issue_type = self.smart_type.get()
            if issue_type == "auto":
                if any(w in line.lower() for w in ["bug", "fix", "broken", "error", "crash", "fail"]):
                    issue_type = "bug"
                elif any(w in line.lower() for w in ["add", "implement", "create", "new", "feature"]):
                    issue_type = "feature"
                else:
                    issue_type = "enhancement"

            prefix = self.smart_prefix.get().strip()
            title = f"{prefix} {line}" if prefix else line

            # Create body with context
            body = f"## Description\n{line}\n\n## Type\n{issue_type.capitalize()}\n\n## Acceptance Criteria\n- [ ] Item completed"

            parsed.append({
                "title": title,
                "body": body,
                "labels": self.smart_labels.get(),
                "assignees": self.smart_assignee.get(),
                "milestone": ""
            })

        if not parsed:
            messagebox.showerror("No issues", "No valid lines found.")
            return

        self.issues_data = parsed
        self._refresh_table()
        messagebox.showinfo("Success", f"✨ Generated {len(parsed)} issues!\n\nNow go to Bulk Import tab to review and create them.")
        self.nb.select(2)

    def _preview_parsed(self):
        raw = self.paste_text.get("1.0", "end").strip()
        if not raw:
            messagebox.showerror("Empty", "Paste some lines first.")
            return

        lines = raw.splitlines()
        preview = f"Found {len(lines)} lines:\n\n"
        for i, line in enumerate(lines[:5], 1):
            preview += f"{i}. {line.strip()}\n"
        if len(lines) > 5:
            preview += f"\n... and {len(lines) - 5} more lines"

        messagebox.showinfo("Preview", preview)

    # ── Tab 5: Template Builder ──────────────
    def _tab_template(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="🛠  Template Builder")

        card = ttk.LabelFrame(f, text="Build a Reusable Issue Template", padding=15)
        card.pack(padx=20, pady=20, fill="both", expand=True)

        ttk.Label(card, text="Template Title Prefix:").grid(row=0, column=0, sticky="w", pady=4)
        self.tmpl_prefix = tk.StringVar(value="[TASK]")
        ttk.Entry(card, textvariable=self.tmpl_prefix, width=40).grid(row=0, column=1, sticky="w", padx=10)

        ttk.Label(card, text="Default Labels:").grid(row=1, column=0, sticky="w", pady=4)
        self.tmpl_labels = tk.StringVar()
        ttk.Entry(card, textvariable=self.tmpl_labels, width=40).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Label(card, text="Default Assignees:").grid(row=2, column=0, sticky="w", pady=4)
        self.tmpl_assignees = tk.StringVar()
        ttk.Entry(card, textvariable=self.tmpl_assignees, width=40).grid(row=2, column=1, sticky="w", padx=10)

        ttk.Label(card, text="Body Template (use {{title}}, {{index}} as placeholders):").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.tmpl_body = scrolledtext.ScrolledText(card, height=8, bg="#161b22", fg="#c9d1d9",
                                                   insertbackground="#c9d1d9", relief="flat", font=("Consolas", 10))
        self.tmpl_body.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        self.tmpl_body.insert("end",
            "## Description\n\n{{description}}\n\n## Acceptance Criteria\n- [ ] Criterion 1\n- [ ] Criterion 2\n\n## Notes\n")

        ttk.Label(card, text="Titles (one per line):").grid(row=5, column=0, sticky="nw", pady=4)
        self.tmpl_titles = scrolledtext.ScrolledText(card, height=5, bg="#161b22", fg="#c9d1d9",
                                                     insertbackground="#c9d1d9", relief="flat", font=("Consolas", 10))
        self.tmpl_titles.grid(row=5, column=1, sticky="nsew", padx=5, pady=5)

        btn_r = ttk.Frame(card)
        btn_r.grid(row=6, column=0, columnspan=2, sticky="e", pady=8)
        ttk.Button(btn_r, text="⚙ Generate & Load into Bulk Tab",
                   command=self._generate_from_template).pack(side="right", padx=5)
        ttk.Button(btn_r, text="💾 Export as JSON",
                   command=self._export_template_json).pack(side="right", padx=5)

        card.columnconfigure(1, weight=1)
        card.rowconfigure(4, weight=1)

    # ── Tab 6: Log ───────────────────────────
    def _tab_log(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text="📋  Activity Log")

        top = ttk.Frame(f)
        top.pack(fill="x", padx=10, pady=5)
        ttk.Button(top, text="🗑 Clear Log", command=self._clear_log).pack(side="right")
        ttk.Button(top, text="💾 Save Log", command=self._save_log).pack(side="right", padx=5)

        self.log_box = scrolledtext.ScrolledText(f, bg="#0d1117", fg="#c9d1d9",
                                                 insertbackground="#c9d1d9", relief="flat",
                                                 font=("Consolas", 10), state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=5)
        self.log_box.tag_config("ok", foreground="#3fb950")
        self.log_box.tag_config("err", foreground="#f85149")
        self.log_box.tag_config("info", foreground="#58a6ff")
        self.log_box.tag_config("warn", foreground="#d29922")

    # ── API / Logic ──────────────────────────
    def _log(self, msg, tag="info"):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        self.nb.select(5)

    def _connect(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a token.")
            return
        self.api = GitHubAPI(token)
        r = self.api.get_user()
        if r.ok:
            user = r.json()["login"]
            self.status_lbl.config(text=f"● Connected as @{user}", fg="#3fb950")
            self._log(f"✅ Authenticated as @{user}", "ok")
            self._refresh_meta()
        else:
            self.status_lbl.config(text="● Auth failed", fg="#da3633")
            self._log(f"❌ Auth failed: {r.status_code} {r.text}", "err")
            messagebox.showerror("Auth Failed", f"HTTP {r.status_code}\n{r.json().get('message','')}")

    def _load_repos(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("Error", "Enter token first.")
            return
        self.api = GitHubAPI(token)
        repos = self.api.get_repos()
        names = [f"{r['full_name']}" for r in repos]
        self.repo_combo["values"] = names
        self._log(f"📦 Loaded {len(names)} repos", "info")

    def _refresh_meta(self):
        repo = self.repo_var.get().strip()
        if not repo or "/" not in repo or not self.api:
            return
        owner, rname = repo.split("/", 1)
        labels = self.api.get_labels(owner, rname)
        self.labels_cache = [l["name"] for l in labels if isinstance(labels, list)]
        milestones = self.api.get_milestones(owner, rname)
        self.milestone_map = {m["title"]: m["number"] for m in milestones if isinstance(milestones, list)}
        assignees = self.api.get_assignees(owner, rname)
        self.assignees_cache = [a["login"] for a in assignees if isinstance(assignees, list)]
        self.s_milestone_combo["values"] = list(self.milestone_map.keys())
        self._log(f"🏷 Labels: {self.labels_cache}", "info")
        self._log(f"👥 Assignees: {self.assignees_cache}", "info")
        self._log(f"🚩 Milestones: {list(self.milestone_map.keys())}", "info")

    def _build_payload(self, title, body="", labels="", assignees="", milestone=""):
        payload = {"title": title.strip(), "body": body.strip()}
        if labels:
            payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
        if assignees:
            payload["assignees"] = [a.strip() for a in assignees.split(",") if a.strip()]
        if milestone and milestone in self.milestone_map:
            payload["milestone"] = self.milestone_map[milestone]
        return payload

    def _create_single(self):
        if not self._check_ready():
            return
        title = self.single_vars["s_title"].get().strip()
        if not title:
            messagebox.showerror("Error", "Title is required.")
            return
        payload = self._build_payload(
            title,
            self.s_body.get("1.0", "end").strip(),
            self.single_vars["s_labels"].get(),
            self.single_vars["s_assignees"].get(),
            self.s_milestone_combo.get()
        )
        if self.s_dry.get():
            self._log(f"[DRY RUN] Would create: {json.dumps(payload, indent=2)}", "warn")
            messagebox.showinfo("Dry Run", f"Payload:\n{json.dumps(payload, indent=2)}")
            return
        owner, rname = self.repo_var.get().split("/", 1)
        r = self.api.create_issue(owner, rname, payload)
        if r.ok:
            url = r.json().get("html_url", "")
            self._log(f"✅ Created: {title} → {url}", "ok")
            messagebox.showinfo("Success", f"Issue created!\n{url}")
        else:
            self._log(f"❌ Failed: {r.status_code} {r.text}", "err")
            messagebox.showerror("Failed", r.text)

    def _check_ready(self):
        if not self.api:
            messagebox.showerror("Not connected", "Please connect first.")
            return False
        repo = self.repo_var.get().strip()
        if not repo or "/" not in repo:
            messagebox.showerror("No repo", "Set a repository in Connect tab.")
            return False
        return True

    # ── CSV / JSON ───────────────────────────
    def _load_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.issues_data = [dict(row) for row in reader]
        self._refresh_table()

    def _load_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if not path:
            return
        with open(path, encoding="utf-8") as f:
            self.issues_data = json.load(f)
        self._refresh_table()

    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for issue in self.issues_data:
            self.tree.insert("", "end", values=(
                issue.get("title", ""),
                (issue.get("body", "") or "")[:60] + "…" if len(issue.get("body", "") or "") > 60 else issue.get("body", ""),
                issue.get("labels", ""),
                issue.get("assignees", ""),
                issue.get("milestone", ""),
            ))
        n = len(self.issues_data)
        self.issues_count_lbl.config(text=f"{n} issue(s) loaded")
        self._log(f"📥 Loaded {n} issues", "info")

    def _clear_issues(self):
        self.issues_data = []
        self._refresh_table()

    def _delete_row(self):
        sel = self.tree.selection()
        for item in sel:
            idx = self.tree.index(item)
            self.tree.delete(item)
            del self.issues_data[idx]
        self.issues_count_lbl.config(text=f"{len(self.issues_data)} issue(s) loaded")

    def _show_ctx(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.ctx_menu.post(event.x_root, event.y_root)

    def _bulk_create(self):
        if not self._check_ready():
            return
        if not self.issues_data:
            messagebox.showerror("No issues", "Load issues first.")
            return
        threading.Thread(target=self._bulk_worker, daemon=True).start()

    def _bulk_worker(self):
        owner, rname = self.repo_var.get().split("/", 1)
        total = len(self.issues_data)
        self.progress["maximum"] = total
        dry = self.dry_run_var.get()
        delay = self.delay_var.get()
        ok_count, fail_count = 0, 0

        for i, issue in enumerate(self.issues_data):
            payload = self._build_payload(
                issue.get("title", f"Issue {i+1}"),
                issue.get("body", ""),
                issue.get("labels", ""),
                issue.get("assignees", ""),
                issue.get("milestone", ""),
            )
            if dry:
                self._log(f"[DRY {i+1}/{total}] {payload['title']}", "warn")
            else:
                r = self.api.create_issue(owner, rname, payload)
                if r.ok:
                    url = r.json().get("html_url", "")
                    self._log(f"✅ [{i+1}/{total}] {payload['title']} → {url}", "ok")
                    ok_count += 1
                else:
                    self._log(f"❌ [{i+1}/{total}] {payload['title']} → {r.status_code}: {r.text}", "err")
                    fail_count += 1
            self.progress["value"] = i + 1
            self.prog_lbl.config(text=f"{i+1} / {total}")
            time.sleep(delay)

        msg = f"Done! ✅ {ok_count} created  ❌ {fail_count} failed" if not dry else f"Dry run complete: {total} issues previewed"
        self._log(msg, "ok")
        messagebox.showinfo("Complete", msg)

    # ── Templates ────────────────────────────
    def _generate_from_template(self):
        titles_raw = self.tmpl_titles.get("1.0", "end").strip().splitlines()
        titles = [t.strip() for t in titles_raw if t.strip()]
        if not titles:
            messagebox.showerror("Error", "Enter at least one title.")
            return
        body_tmpl = self.tmpl_body.get("1.0", "end")
        prefix = self.tmpl_prefix.get().strip()
        self.issues_data = []
        for i, title in enumerate(titles):
            full_title = f"{prefix} {title}" if prefix else title
            body = body_tmpl.replace("{{title}}", title).replace("{{index}}", str(i+1)).replace("{{description}}", title)
            self.issues_data.append({
                "title": full_title,
                "body": body,
                "labels": self.tmpl_labels.get(),
                "assignees": self.tmpl_assignees.get(),
                "milestone": ""
            })
        self._refresh_table()
        self.nb.select(2)
        messagebox.showinfo("Generated", f"{len(titles)} issues generated and loaded into Bulk tab.")

    def _export_template_json(self):
        if not self.issues_data:
            self._generate_from_template()
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.issues_data, f, indent=2)
            self._log(f"💾 Exported to {path}", "ok")

    def _download_csv_template(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                             initialfile="issues_template.csv",
                                             filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["title", "body", "labels", "assignees", "milestone"])
                writer.writeheader()
                writer.writerow({
                    "title": "Example Issue Title",
                    "body": "## Description\n\nDescribe the issue here.",
                    "labels": "bug,enhancement",
                    "assignees": "github-username",
                    "milestone": "v1.0"
                })
            self._log(f"💾 CSV template saved to {path}", "ok")

    def _download_json_template(self):
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                             initialfile="issues_template.json",
                                             filetypes=[("JSON", "*.json")])
        if path:
            data = [
                {
                    "title": "Example Issue 1",
                    "body": "## Description\n\nDescribe the issue here.\n\n## Steps to Reproduce\n1. Step one\n2. Step two",
                    "labels": "bug",
                    "assignees": "github-username",
                    "milestone": ""
                },
                {
                    "title": "Example Issue 2",
                    "body": "## Feature Request\n\nDescribe the feature.",
                    "labels": "enhancement",
                    "assignees": "",
                    "milestone": "v1.0"
                }
            ]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._log(f"💾 JSON template saved to {path}", "ok")

    def _clear_log(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_box.get("1.0", "end"))


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = BulkIssueApp()
    app.mainloop()
