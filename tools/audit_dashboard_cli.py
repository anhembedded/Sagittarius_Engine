import argparse
import json
import sys
import time
import urllib.request

try:
    from rich import box
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def fetch_telemetry(port: int, path: str = "/") -> dict | None:
    try:
        req = urllib.request.Request(f"http://localhost:{port}{path}")
        with urllib.request.urlopen(req, timeout=1.0) as response:
            return json.loads(response.read().decode())
    except Exception:
        return None


def generate_ui(port: int):
    data = fetch_telemetry(port)
    if not data:
        return Panel(
            f"[red]🔴 Connection Error[/red]\nCannot connect to Engine at [b]http://localhost:{port}[/b].\n"
            "Make sure the engine is running and `AuditExtension(enable_dashboard=True)` is registered.",
            title="Sagittarius Engine Audit Dashboard",
            border_style="red",
            box=box.ROUNDED,
        )

    # 1. Background Tasks & Scheduler
    tasks = data.get("tasks", [])
    jobs = data.get("scheduler", [])

    table = Table(
        title="Background Tasks", box=box.ROUNDED, expand=True, border_style="blue"
    )
    table.add_column("Task ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Status")
    table.add_column("Runtime", justify="right", style="green")

    for t in tasks:
        status = t.get("status", "Unknown")
        if status == "running":
            status_str = f"[bold green]▶ {status}[/bold green]"
        elif status == "completed":
            status_str = f"[bold blue]✓ {status}[/bold blue]"
        elif status == "failed":
            status_str = f"[bold red]✗ {status}[/bold red]"
        else:
            status_str = status
        table.add_row(t.get("id"), t.get("name"), status_str, t.get("runtime"))

    if not tasks:
        table.add_row("", "No background tasks", "", "")

    scheduler_table = Table(
        title="Scheduled Jobs", box=box.ROUNDED, expand=True, border_style="yellow"
    )
    scheduler_table.add_column("Job Name", style="magenta")
    scheduler_table.add_column("Interval", style="cyan")
    scheduler_table.add_column("Next Run", style="green")

    for j in jobs:
        scheduler_table.add_row(j.get("name"), j.get("interval"), j.get("next_run"))
    if not jobs:
        scheduler_table.add_row("No scheduled jobs", "", "")

    # 2. Overview
    uptime = data.get("uptime", 0.0)
    health = data.get("health", {})
    env = data.get("environment", {})
    health_status = health.get("status", "unknown").upper()
    health_color = "green" if health_status == "HEALTHY" else "red"

    overview_parts = [
        f"[b]Uptime:[/b] {uptime:.1f}s | [b]Status:[/b] [{health_color}][b]{health_status}[/b][/{health_color}]\n",
        f"[b]OS:[/b] {env.get('os')} {env.get('os_release')} | [b]Python:[/b] {env.get('python_version')}\n",
        f"[b]CPU:[/b] {env.get('cpu_percent')} | [b]RAM:[/b] {env.get('ram_mb')}\n\n",
    ]
    for comp, stat in health.get("components", {}).items():
        icon = "✅" if stat == "ok" else "❌"
        overview_parts.append(f"{icon} [b]{comp}[/b]: {stat}\n")
    overview_text = "".join(overview_parts)

    overview_panel = Panel(
        overview_text, title="System Overview", border_style="cyan", box=box.ROUNDED
    )

    # 3. Extensions & Pipeline
    exts = data.get("extensions", [])
    srvs = data.get("services", [])
    pipeline = data.get("pipeline", [])

    ext_text = "[bold blue]Middleware Pipeline[/bold blue]\n"
    if not pipeline:
        ext_text += "*No middlewares registered.*\n"
    for i, p in enumerate(pipeline):
        ext_text += f"{i + 1}. [yellow]{p}[/yellow]\n"

    ext_text += "\n[bold blue]Loaded Extensions[/bold blue]\n"
    for e in exts:
        icon = "✅" if e.get("enabled") else "❌"
        ext_text += f"{icon} [b]{e.get('name')}[/b] (v{e.get('version')})\n"

    ext_text += "\n[bold blue]Hosted Services[/bold blue]\n"
    if not srvs:
        ext_text += "*No background hosted services are currently running.*\n"
    for s in srvs:
        ext_text += f"🟢 [b]{s}[/b]\n"

    ext_panel = Panel(
        ext_text, title="Extensions & Pipeline", border_style="yellow", box=box.ROUNDED
    )

    # 4. Event Bus & Stream
    config_bus = data.get("config_bus", {})
    eb_handlers = config_bus.get("event_bus_handlers", {})
    config_keys = config_bus.get("config_keys", [])
    recent_events = data.get("recent_events", [])

    cb_text = "[bold blue]Live Event Stream[/bold blue]\n"
    if not recent_events:
        cb_text += "*No events emitted yet.*\n"
    for rev in reversed(recent_events):
        cb_text += f"⚡ {rev}\n"

    cb_text += "\n[bold blue]Event Bus[/bold blue]\n"
    if not eb_handlers:
        cb_text += "*No events registered.*\n"
    for ev, count in eb_handlers.items():
        cb_text += f"📨 [b]{ev}[/b]: {count} handler(s)\n"

    cb_text += "\n[bold blue]Config Keys[/bold blue]\n"
    if not config_keys:
        cb_text += "*No config keys loaded.*\n"
    for k in config_keys:
        cb_text += f"🎛️ {k}\n"

    cb_panel = Panel(
        cb_text, title="Event Bus & Config", border_style="magenta", box=box.ROUNDED
    )

    # 5. Assemble Layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )

    active_tasks = len([t for t in tasks if t.get("status") == "running"])
    header_text = f"[bold white]🚀 Sagittarius Engine Dashboard[/bold white] | Port: [yellow]{port}[/yellow] | Active Tasks: [green]{active_tasks}[/green]"
    layout["header"].update(Panel(header_text, box=box.ROUNDED, border_style="blue"))

    layout["main"].split_row(
        Layout(name="left", ratio=2), Layout(name="right", ratio=1)
    )

    layout["left"].split_column(Layout(name="tasks"), Layout(name="scheduler"))
    layout["left"]["tasks"].update(table)
    layout["left"]["scheduler"].update(scheduler_table)

    layout["right"].split_column(
        Layout(name="overview", ratio=1),
        Layout(name="extensions", ratio=1),
        Layout(name="config", ratio=1),
    )
    layout["right"]["overview"].update(overview_panel)
    layout["right"]["extensions"].update(ext_panel)
    layout["right"]["config"].update(cb_panel)

    layout["footer"].update(
        Panel(
            "Press [bold red]Ctrl+C[/bold red] to quit",
            box=box.ROUNDED,
            border_style="red",
        )
    )

    return layout


def walk_dict(tree: Tree, dictionary: dict):
    for k, v in dictionary.items():
        if isinstance(v, dict):
            branch = tree.add(f"[bold cyan]{k}[/bold cyan]")
            walk_dict(branch, v)
        elif isinstance(v, list):
            branch = tree.add(f"[bold cyan]{k}[/bold cyan] ([i]list[/i])")
            for item in v:
                if isinstance(item, dict):
                    sub = branch.add("[i]dict[/i]")
                    walk_dict(sub, item)
                else:
                    branch.add(str(item))
        else:
            tree.add(f"[bold cyan]{k}[/bold cyan]: {v}")


def generate_config_ui(port: int):
    data = fetch_telemetry(port, "/config")
    if not data:
        return Panel(
            f"[red]🔴 Connection Error[/red]\nCannot connect to Engine at `http://localhost:{port}/config`.",
            title="Error",
            border_style="red",
        )

    config_dict = data.get("config", {})
    tree = Tree("📁 [bold magenta]Global Configuration[/bold magenta]")
    walk_dict(tree, config_dict)
    return Panel(tree, title="Config Explorer", border_style="cyan", box=box.ROUNDED)


def generate_events_ui(port: int):
    data = fetch_telemetry(port, "/events")
    if not data:
        return Panel(
            "[red]🔴 Connection Error[/red]\nCannot connect to Engine.",
            title="Error",
            border_style="red",
        )

    events = data.get("events", [])
    table = Table(
        title="Live Event Stream (Last 100)",
        box=box.ROUNDED,
        expand=True,
        border_style="magenta",
    )
    table.add_column("Timestamp & Event Name", style="bold green")

    for rev in reversed(events):
        table.add_row(f"⚡ {rev}")

    if not events:
        table.add_row("No events emitted yet")

    return table


def generate_tasks_ui(port: int):
    data = fetch_telemetry(port, "/tasks")
    if not data:
        return Panel(
            "[red]🔴 Connection Error[/red]\nCannot connect to Engine.",
            title="Error",
            border_style="red",
        )

    tasks = data.get("tasks", [])
    table = Table(
        title="Task Manager", box=box.ROUNDED, expand=True, border_style="blue"
    )
    table.add_column("Task ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Status")
    table.add_column("Runtime", justify="right", style="green")
    table.add_column("Error Trace", style="red")

    for t in tasks:
        status = t.get("status", "Unknown")
        if status == "running":
            status_str = f"[bold green]▶ {status}[/bold green]"
        elif status == "completed":
            status_str = f"[bold blue]✓ {status}[/bold blue]"
        elif status == "failed":
            status_str = f"[bold red]✗ {status}[/bold red]"
        else:
            status_str = status

        error_msg = t.get("error") or ""
        table.add_row(
            t.get("id"), t.get("name"), status_str, t.get("runtime"), error_msg
        )

    if not tasks:
        table.add_row("", "No background tasks", "", "", "")

    return table


def main():
    if not RICH_AVAILABLE:
        print("❌ Error: 'rich' is not installed.")
        print("Please run: pip install rich")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Sagittarius Audit Dashboard")
    parser.add_argument("--port", type=int, default=9999, help="Telemetry server port")
    parser.add_argument(
        "--view",
        type=str,
        default="summary",
        choices=["summary", "config", "events", "tasks"],
        help="Dashboard view to display",
    )
    args = parser.parse_args()

    console = Console()
    console.clear()

    def get_ui():
        if args.view == "config":
            return generate_config_ui(args.port)
        if args.view == "events":
            return generate_events_ui(args.port)
        if args.view == "tasks":
            return generate_tasks_ui(args.port)
        return generate_ui(args.port)

    try:
        with Live(get_ui(), refresh_per_second=1, screen=True) as live:
            while True:
                time.sleep(1.0)
                live.update(get_ui())
    except KeyboardInterrupt:
        console.print("[bold green]Dashboard stopped gracefully.[/bold green]")


if __name__ == "__main__":
    main()
