#!/usr/bin/env python3
"""Process Watcher TUI - Interactive process monitor with search and sorting."""

import time
from collections import namedtuple
from typing import Optional

try:
    import psutil
except ImportError:
    print("psutil required. Install with: pip install psutil")
    exit(1)

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical
    from textual.widgets import Footer, Static, Input, Button, Label
    from textual.binding import Binding
    from textual.reactive import reactive
    from textual.message import Message
    from textual.screen import Screen
    from textual import events
except ImportError:
    print("textual required. Install with: pip install textual")
    exit(1)

Proc = namedtuple("Proc", ["pid", "cpu", "mem", "cmd"])


class ProcessList(Static):
    """Widget to display the list of processes."""
    
    processes = reactive([])
    search_filter = reactive("")
    sort_by = reactive("cpu")
    sort_reverse = reactive(True)
    selected_index = reactive(0)
    expanded_index = reactive(-1)  # Index of process with expanded command (-1 = none)
    
    class ProcessSelected(Message):
        """Message sent when a process is selected."""
        def __init__(self, proc: Proc) -> None:
            self.proc = proc
            super().__init__()
    
    def __init__(self, count: int = 30, **kwargs):
        super().__init__(**kwargs)
        self.count = count
        self._displayed_procs = []
    
    def watch_search_filter(self, search: str) -> None:
        """Re-filter when search changes."""
        self._update_display()
        self.selected_index = 0
    
    def watch_sort_by(self, sort: str) -> None:
        """Re-sort when sort changes."""
        self._update_display()
    
    def watch_sort_reverse(self, reverse: bool) -> None:
        """Re-sort when sort direction changes."""
        self._update_display()
    
    def update_processes(self, procs: list[Proc]) -> None:
        """Update the process list."""
        self.processes = procs
        self._update_display()
    
    def _update_display(self) -> None:
        """Update the displayed process list."""
        # Filter
        if self.search_filter:
            search_lower = self.search_filter.lower()
            filtered = [p for p in self.processes 
                       if search_lower in p.cmd.lower() 
                       or search_lower in str(p.pid)]
        else:
            filtered = list(self.processes)
        
        # Sort
        sort_key = {
            "cpu": lambda p: p.cpu,
            "mem": lambda p: p.mem,
            "pid": lambda p: p.pid,
            "cmd": lambda p: p.cmd.lower(),
        }.get(self.sort_by, lambda p: p.cpu)
        
        filtered.sort(key=sort_key, reverse=self.sort_reverse)
        
        # Limit
        self._displayed_procs = filtered[:self.count]
        self._refresh_display()
    
    def _refresh_display(self) -> None:
        """Render the process list."""
        lines = []
        
        # Header
        sort_indicator = "↓" if self.sort_reverse else "↑"
        cpu_header = f"CPU%{sort_indicator}" if self.sort_by == "cpu" else "CPU%"
        mem_header = f"MEM%{sort_indicator}" if self.sort_by == "mem" else "MEM%"
        pid_header = f"PID{sort_indicator}" if self.sort_by == "pid" else "PID"
        cmd_header = f"COMMAND{sort_indicator}" if self.sort_by == "cmd" else "COMMAND"
        
        header = f"[bold #89b4fa]{pid_header:>8}  {cpu_header:>6}  {mem_header:>6}  {cmd_header}[/]"
        lines.append(header)
        lines.append("[#6c7086]" + "─" * 60 + "[/]")
        
        # Clamp selected index
        if self._displayed_procs:
            self.selected_index = max(0, min(self.selected_index, len(self._displayed_procs) - 1))
        
        # Process lines
        for i, proc in enumerate(self._displayed_procs):
            cpu_str = f"{proc.cpu:>5.1f}%"
            mem_str = f"{proc.mem:>5.1f}%"
            
            # Truncate command if too long (unless expanded)
            cmd = proc.cmd
            if len(cmd) > 60 and i != self.expanded_index:
                cmd = cmd[:57] + "..."
            
            line = f"{proc.pid:>8}  {cpu_str:>6}  {mem_str:>6}  {cmd}"
            
            if i == self.selected_index:
                lines.append(f"[reverse]{line}[/]")
            else:
                lines.append(line)
        
        if not self._displayed_procs:
            if self.search_filter:
                lines.append("[#6c7086]No matching processes[/]")
            else:
                lines.append("[#6c7086]No processes found[/]")
        
        self.update("\n".join(lines))
    
    def on_mouse_up(self, event: events.MouseUp) -> None:
        """Handle mouse up events for column sorting and command expansion."""
        x = event.x - 2  # Account for horizontal padding
        
        # Header is at y=1 due to padding (padding: 1 2 in CSS)
        if event.y == 1:
            # Column positions based on header format: "     PID   CPU%↓    MEM%  COMMAND"
            # PID: 0-8, CPU: 10-16, MEM: 18-24, CMD: 26+
            if x < 10:
                col = "pid"
            elif x < 18:
                col = "cpu"
            elif x < 26:
                col = "mem"
            else:
                col = "cmd"
            
            if self.sort_by == col:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_by = col
                self.sort_reverse = True
            self._refresh_display()
            event.stop()
        
        # Process rows start at y=3 (y=2 is separator line)
        elif event.y >= 3 and x >= 26:
            row_index = event.y - 3  # Convert y to process index
            if 0 <= row_index < len(self._displayed_procs):
                # Toggle expansion for this row
                if self.expanded_index == row_index:
                    self.expanded_index = -1  # Collapse
                else:
                    self.expanded_index = row_index  # Expand
                self._refresh_display()
                event.stop()
    
    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "up":
            if self.selected_index > 0:
                self.selected_index -= 1
                self._refresh_display()
                event.stop()
        elif event.key == "down":
            if self.selected_index < len(self._displayed_procs) - 1:
                self.selected_index += 1
                self._refresh_display()
                event.stop()
        elif event.key == "enter":
            if self._displayed_procs and 0 <= self.selected_index < len(self._displayed_procs):
                self.post_message(self.ProcessSelected(self._displayed_procs[self.selected_index]))
                event.stop()
    
    def get_selected(self) -> Optional[Proc]:
        """Get the currently selected process."""
        if self._displayed_procs and 0 <= self.selected_index < len(self._displayed_procs):
            return self._displayed_procs[self.selected_index]
        return None


class SearchBar(Container):
    """Search input bar."""
    
    def compose(self) -> ComposeResult:
        yield Label("Search:", classes="search-label")
        yield Input(placeholder="Filter by PID or command...", id="search-input")


class HelpScreen(Screen):
    """Help/controls screen."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("q", "app.quit", "Quit", priority=True),
    ]
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold #cba6f7]Process Watcher TUI - Help[/]\n", classes="help-title"),
            Static("""
[bold]Navigation[/]
  ↑/k       Move selection up
  ↓/j       Move selection down
  Enter     Show process details
  g         Go to top
  G         Go to bottom

[bold]Search & Filter[/]
  /         Toggle search bar
  Esc       Clear search / close search
  r         Refresh now

[bold]Sorting[/]
  c         Sort by CPU%
  m         Sort by MEM%
  p         Sort by PID
  n         Sort by name
  s         Toggle sort direction (asc/desc)

[bold]General[/]
  q         Quit
  ?         Show this help
            """, classes="help-content"),
            classes="help-container"
        )


class DetailScreen(Screen):
    """Screen showing process details."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Close"),
        Binding("q", "app.quit", "Quit", priority=True),
        Binding("k", "app.kill_process", "Kill Process"),
    ]
    
    proc: reactive[Optional[Proc]] = reactive(None)
    
    def __init__(self, proc: Proc, **kwargs):
        super().__init__(**kwargs)
        self.proc = proc
    
    def compose(self) -> ComposeResult:
        yield Container(
            Static("[bold #cba6f7]Process Details[/]\n", classes="detail-title"),
            Static("", id="detail-content"),
            classes="detail-container"
        )
    
    def on_mount(self) -> None:
        """Render details when mounted."""
        self._render_details()
    
    def _render_details(self) -> None:
        """Render process details."""
        if not self.proc:
            return
        
        proc = self.proc
        try:
            p = psutil.Process(proc.pid)
            create_time = time.strftime("%Y-%m-%d %H:%M:%S", 
                                        time.localtime(p.create_time()))
            status = p.status()
            num_threads = p.num_threads()
            try:
                username = p.username()
            except psutil.AccessDenied:
                username = "N/A"
            try:
                exe = p.exe()
            except psutil.AccessDenied:
                exe = "N/A"
            
            # Get memory info
            mem_info = p.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            
        except psutil.NoSuchProcess:
            content = f"[#f38ba8]Process {proc.pid} no longer exists[/]"
            self.query_one("#detail-content", Static).update(content)
            return
        except psutil.AccessDenied:
            content = f"[#f9e2af]Access denied to process {proc.pid}[/]"
            self.query_one("#detail-content", Static).update(content)
            return
        
        content = f"""
[bold]PID:[/]     {proc.pid}
[bold]CPU:[/]     {proc.cpu:.1f}%
[bold]Memory:[/]  {proc.mem:.1f}% ({mem_mb:.1f} MB)
[bold]Status:[/]  {status}
[bold]User:[/]    {username}
[bold]Threads:[/] {num_threads}
[bold]Started:[/] {create_time}

[bold]Executable:[/]
  {exe}

[bold]Command Line:[/]
  {proc.cmd}

[bold]Actions:[/]
  Press [bold]k[/] to kill this process
"""
        self.query_one("#detail-content", Static).update(content)


class ProcessWatcherApp(App):
    """Main TUI application."""
    
    # Catppuccin Mocha color palette
    COLORS = """
    $rosewater: #f5e0dc;
    $flamingo: #f2cdcd;
    $pink: #f5c2e7;
    $mauve: #cba6f7;
    $red: #f38ba8;
    $maroon: #eba0ac;
    $peach: #fab387;
    $yellow: #f9e2af;
    $green: #a6e3a1;
    $teal: #94e2d5;
    $sky: #89dceb;
    $sapphire: #74c7ec;
    $blue: #89b4fa;
    $lavender: #b4befe;
    $text: #cdd6f4;
    $subtext1: #bac2de;
    $subtext0: #a6adc8;
    $overlay2: #9399b2;
    $overlay1: #7f849c;
    $overlay0: #6c7086;
    $surface2: #585b70;
    $surface1: #45475a;
    $surface0: #313244;
    $base: #1e1e2e;
    $mantle: #181825;
    $crust: #11111b;
    """
    
    CSS = COLORS + """
    Screen {
        background: $base;
        color: $text;
    }
    
    SearchBar {
        dock: top;
        height: 2;
        padding: 0;
        background: $surface0;
        layout: horizontal;
    }
    
    SearchBar .search-label {
        color: $lavender;
        background: $surface0;
        text-style: bold;
        padding: 0 1;
        margin-right: 0;
        height: 2;
        content-align: center middle;
        border-right: solid $surface1;
    }
    
    SearchBar Input {
        width: 1fr;
        background: $surface0;
        color: $text;
        border: none;
        padding: 0 0 0 1;
        height: 2;
    }
    
    SearchBar Input:focus {
        border-bottom: solid $mauve;
    }
    
    ProcessList {
        padding: 1 2;
        height: 1fr;
    }
    
    .status-bar {
        dock: bottom;
        height: 1;
        background: $mantle;
        padding: 0 2;
        color: $subtext0;
    }
    
    .help-container, .detail-container {
        padding: 2 4;
        margin: 2 4;
        background: $surface0;
        border: solid $mauve;
    }
    
    .help-title, .detail-title {
        text-align: center;
        margin-bottom: 1;
        color: $lavender;
    }
    
    .help-content {
        padding: 1 2;
    }
    
    Footer {
        background: $mantle;
        color: $subtext0;
    }
    
    Header {
        background: $mantle;
        color: $lavender;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "help", "Help"),
        Binding("slash", "toggle_search", "Search"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "sort_cpu", "Sort by CPU"),
        Binding("m", "sort_mem", "Sort by Memory"),
        Binding("p", "sort_pid", "Sort by PID"),
        Binding("n", "sort_name", "Sort by Name"),
        Binding("s", "toggle_sort_dir", "Toggle Sort Dir"),
        Binding("up,k", "cursor_up", "Up", show=False),
        Binding("down,j", "cursor_down", "Down", show=False),
        Binding("g", "go_top", "Top", show=False),
        Binding("G", "go_bottom", "Bottom", show=False),
        Binding("enter", "select", "Select", show=False),
    ]
    
    refresh_rate: reactive[float] = reactive(1.0)
    process_count: reactive[int] = reactive(30)
    
    def __init__(self, refresh_rate: float = 1.0, count: int = 30, **kwargs):
        super().__init__(**kwargs)
        self.refresh_rate = refresh_rate
        self.process_count = count
        self._refresh_timer = None
        self._process_cache: dict[int, psutil.Process] = {}  # Cache processes by PID
    
    def compose(self) -> ComposeResult:
        yield ProcessList(count=self.process_count, id="proc-list")
        yield Footer()
    
    def on_mount(self) -> None:
        """Set up refresh timer on mount."""
        self._refresh_timer = self.set_interval(self.refresh_rate, self._refresh_processes)
        self._refresh_processes()
    
    def on_unmount(self) -> None:
        """Clean up timer."""
        if self._refresh_timer:
            self._refresh_timer.stop()
    
    def _refresh_processes(self) -> None:
        """Fetch and update process list."""
        procs = self._get_processes()
        self.query_one(ProcessList).update_processes(procs)
    
    def _get_processes(self) -> list[Proc]:
        """Get processes using psutil with CPU measurement."""
        procs = []
        new_cache: dict[int, psutil.Process] = {}
        
        for p in psutil.process_iter(["pid", "cmdline", "name"]):
            try:
                pid = p.info["pid"]
                
                # Reuse cached process object if available (for accurate CPU delta)
                if pid in self._process_cache:
                    proc = self._process_cache[pid]
                else:
                    proc = p
                    proc.cpu_percent(interval=0)  # Initialize for next refresh
                
                # Get CPU percent since last call (non-blocking)
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_percent()
                cmd = p.info["cmdline"]
                if cmd:
                    cmd = " ".join(cmd)
                else:
                    cmd = p.info["name"] or "[unknown]"
                
                procs.append(Proc(pid, cpu, mem, cmd))
                new_cache[pid] = proc
                
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Update cache (removes stale processes automatically)
        self._process_cache = new_cache
        
        return procs
    
    # Actions
    def action_toggle_search(self) -> None:
        """Toggle search bar."""
        try:
            search_bar = self.query_one(SearchBar)
            # Remove it
            search_bar.remove()
            self.query_one(ProcessList).search_filter = ""
        except Exception:
            # Add it at the top
            search_bar = SearchBar()
            self.mount(search_bar, before=self.query_one(ProcessList))
            search_bar.query_one(Input).focus()
    
    def action_refresh(self) -> None:
        """Force refresh."""
        self._refresh_processes()
    
    def action_sort_cpu(self) -> None:
        """Sort by CPU."""
        proc_list = self.query_one(ProcessList)
        if proc_list.sort_by == "cpu":
            proc_list.sort_reverse = not proc_list.sort_reverse
        else:
            proc_list.sort_by = "cpu"
            proc_list.sort_reverse = True
    
    def action_sort_mem(self) -> None:
        """Sort by memory."""
        proc_list = self.query_one(ProcessList)
        if proc_list.sort_by == "mem":
            proc_list.sort_reverse = not proc_list.sort_reverse
        else:
            proc_list.sort_by = "mem"
            proc_list.sort_reverse = True
    
    def action_sort_pid(self) -> None:
        """Sort by PID."""
        proc_list = self.query_one(ProcessList)
        if proc_list.sort_by == "pid":
            proc_list.sort_reverse = not proc_list.sort_reverse
        else:
            proc_list.sort_by = "pid"
            proc_list.sort_reverse = False
    
    def action_sort_name(self) -> None:
        """Sort by name."""
        proc_list = self.query_one(ProcessList)
        if proc_list.sort_by == "cmd":
            proc_list.sort_reverse = not proc_list.sort_reverse
        else:
            proc_list.sort_by = "cmd"
            proc_list.sort_reverse = False
    
    def action_toggle_sort_dir(self) -> None:
        """Toggle sort direction."""
        proc_list = self.query_one(ProcessList)
        proc_list.sort_reverse = not proc_list.sort_reverse
    
    def action_cursor_up(self) -> None:
        """Move cursor up."""
        self.query_one(ProcessList).on_key(events.Key(key="up"))
    
    def action_cursor_down(self) -> None:
        """Move cursor down."""
        self.query_one(ProcessList).on_key(events.Key(key="down"))
    
    def action_go_top(self) -> None:
        """Go to top of list."""
        proc_list = self.query_one(ProcessList)
        proc_list.selected_index = 0
        proc_list._refresh_display()
    
    def action_go_bottom(self) -> None:
        """Go to bottom of list."""
        proc_list = self.query_one(ProcessList)
        if proc_list._displayed_procs:
            proc_list.selected_index = len(proc_list._displayed_procs) - 1
            proc_list._refresh_display()
    
    def action_select(self) -> None:
        """Select current process."""
        proc_list = self.query_one(ProcessList)
        selected = proc_list.get_selected()
        if selected:
            self.push_screen(DetailScreen(selected))
    
    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())
    
    def action_kill_process(self) -> None:
        """Kill the selected process (from detail screen)."""
        if isinstance(self.screen, DetailScreen) and self.screen.proc:
            try:
                p = psutil.Process(self.screen.proc.pid)
                p.terminate()
                self.notify(f"Terminated process {self.screen.proc.pid}", title="Process Killed")
                self.pop_screen()
                self._refresh_processes()
            except psutil.NoSuchProcess:
                self.notify("Process no longer exists", severity="error")
                self.pop_screen()
            except psutil.AccessDenied:
                self.notify("Access denied - need higher privileges", severity="error")
            except Exception as e:
                self.notify(f"Failed to kill process: {e}", severity="error")
    
    # Event handlers
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.query_one(ProcessList).search_filter = event.value
    
    def on_key(self, event: events.Key) -> None:
        """Handle global key events."""
        # Quit on 'q'
        if event.key == "q":
            self.exit()
            event.stop()
        # Handle escape for search
        elif event.key == "escape":
            try:
                search_bar = self.query_one(SearchBar)
                search_bar.remove()
                self.query_one(ProcessList).search_filter = ""
                event.stop()
            except Exception:
                pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Process Watcher TUI")
    parser.add_argument("-n", "--count", type=int, default=30, 
                       help="Number of processes to show (default: 30)")
    parser.add_argument("-r", "--rate", type=float, default=1.0, 
                       help="Refresh rate in seconds (default: 1.0)")
    args = parser.parse_args()
    
    app = ProcessWatcherApp(refresh_rate=args.rate, count=args.count)
    app.run()


if __name__ == "__main__":
    main()
