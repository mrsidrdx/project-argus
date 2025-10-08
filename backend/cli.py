#!/usr/bin/env python3
"""
Aegis CLI - Command-line interface for policy management and decision monitoring.
"""

import os
import sys
import json
import time
import yaml
import click
import requests
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime


# Configuration
DEFAULT_API_BASE = "http://localhost:8080"
DEFAULT_POLICY_DIR = "./policies"


class AegisCLI:
    """Main CLI class for Aegis operations."""
    
    def __init__(self, api_base: str, api_key: str = None):
        self.api_base = api_base.rstrip('/')
        self.api_key = api_key or os.getenv("AEGIS_API_KEY", "admin-key-change-in-production")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make an authenticated request to the API."""
        url = f"{self.api_base}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except requests.exceptions.RequestException as e:
            click.echo(f"❌ API request failed: {e}", err=True)
            sys.exit(1)
    
    def get_agents(self) -> List[str]:
        """Get all agents from the API."""
        response = self._make_request("GET", "/admin/agents")
        if response.status_code == 200:
            return response.json().get("agents", [])
        else:
            click.echo(f"❌ Failed to get agents: {response.status_code} {response.text}", err=True)
            return []
    
    def get_policies(self) -> Dict[str, Any]:
        """Get policies summary from the API."""
        response = self._make_request("GET", "/admin/policies")
        if response.status_code == 200:
            return response.json()
        else:
            click.echo(f"❌ Failed to get policies: {response.status_code} {response.text}", err=True)
            return {}
    
    def get_decisions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent decisions from the API."""
        response = self._make_request("GET", f"/admin/decisions?limit={limit}")
        if response.status_code == 200:
            return response.json().get("decisions", [])
        else:
            click.echo(f"❌ Failed to get decisions: {response.status_code} {response.text}", err=True)
            return []
    
    def test_tool_call(self, agent_id: str, tool: str, action: str, params: Dict[str, Any], parent_agent: str = None) -> Dict[str, Any]:
        """Test a tool call through the gateway."""
        headers = {"X-Agent-ID": agent_id}
        if parent_agent:
            headers["X-Parent-Agent"] = parent_agent
        
        # Remove authorization for tool calls (they don't need admin auth)
        tool_session = requests.Session()
        tool_session.headers.update(headers)
        
        url = f"{self.api_base}/tools/{tool}/{action}"
        try:
            response = tool_session.post(url, json=params)
            return {
                "status_code": response.status_code,
                "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            }
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}


@click.group()
@click.option('--api-base', default=DEFAULT_API_BASE, help='API base URL')
@click.option('--api-key', help='Admin API key (or set AEGIS_API_KEY env var)')
@click.pass_context
def cli(ctx, api_base, api_key):
    """Aegis CLI - Policy management and decision monitoring."""
    ctx.ensure_object(dict)
    ctx.obj['cli'] = AegisCLI(api_base, api_key)


@cli.group()
def policy():
    """Policy management commands."""
    pass


@policy.command()
@click.argument('policy_dir', type=click.Path(exists=True), default=DEFAULT_POLICY_DIR)
def validate(policy_dir):
    """Validate policy files in a directory."""
    click.echo(f"🔍 Validating policies in {policy_dir}...")
    
    policy_path = Path(policy_dir)
    policy_files = list(policy_path.glob("*.yaml"))
    
    if not policy_files:
        click.echo("❌ No policy files found (.yaml)", err=True)
        sys.exit(1)
    
    errors = []
    valid_count = 0
    
    for policy_file in policy_files:
        try:
            with open(policy_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if data is None:
                errors.append(f"{policy_file.name}: Empty file")
                continue
            
            # Basic validation
            if "version" not in data:
                errors.append(f"{policy_file.name}: Missing 'version' field")
            
            if "agents" not in data:
                errors.append(f"{policy_file.name}: Missing 'agents' field")
            elif not isinstance(data["agents"], list):
                errors.append(f"{policy_file.name}: 'agents' must be a list")
            else:
                # Validate agents
                for i, agent in enumerate(data["agents"]):
                    if not isinstance(agent, dict):
                        errors.append(f"{policy_file.name}: Agent {i} must be an object")
                        continue
                    
                    if "id" not in agent:
                        errors.append(f"{policy_file.name}: Agent {i} missing 'id' field")
                    
                    if "allow" not in agent:
                        errors.append(f"{policy_file.name}: Agent {i} missing 'allow' field")
            
            if not errors:
                valid_count += 1
                click.echo(f"✅ {policy_file.name}")
            
        except yaml.YAMLError as e:
            errors.append(f"{policy_file.name}: YAML syntax error - {e}")
        except Exception as e:
            errors.append(f"{policy_file.name}: Validation error - {e}")
    
    if errors:
        click.echo(f"\n❌ Validation failed with {len(errors)} errors:")
        for error in errors:
            click.echo(f"   {error}")
        sys.exit(1)
    else:
        click.echo(f"\n🎯 All {valid_count} policy files are valid!")


@policy.command()
@click.argument('policy_file', type=click.Path(exists=True))
def show(policy_file):
    """Show details of a policy file."""
    try:
        with open(policy_file, 'r') as f:
            data = yaml.safe_load(f)
        
        click.echo(f"📋 Policy: {Path(policy_file).name}")
        click.echo(f"Version: {data.get('version', 'N/A')}")
        
        agents = data.get('agents', [])
        click.echo(f"Agents: {len(agents)}")
        
        for agent in agents:
            click.echo(f"\n🤖 Agent: {agent.get('id', 'Unknown')}")
            if 'description' in agent:
                click.echo(f"   Description: {agent['description']}")
            
            allow_rules = agent.get('allow', [])
            click.echo(f"   Rules: {len(allow_rules)}")
            
            for rule in allow_rules:
                tool = rule.get('tool', 'Unknown')
                actions = ', '.join(rule.get('actions', []))
                click.echo(f"   • {tool}: {actions}")
                
                if rule.get('requires_approval'):
                    click.echo("     ⚠️  Requires approval")
                
                conditions = rule.get('conditions', {})
                if conditions:
                    click.echo("     Conditions:")
                    for key, value in conditions.items():
                        click.echo(f"       - {key}: {value}")
    
    except Exception as e:
        click.echo(f"❌ Error reading policy file: {e}", err=True)
        sys.exit(1)


@cli.group()
def agents():
    """Agent management commands."""
    pass


@agents.command()
@click.pass_context
def list(ctx):
    """List all agents."""
    cli_obj = ctx.obj['cli']
    agents = cli_obj.get_agents()
    
    if agents:
        click.echo(f"🤖 Found {len(agents)} agents:")
        for agent in sorted(agents):
            click.echo(f"   • {agent}")
    else:
        click.echo("No agents found")


@agents.command()
@click.pass_context
def summary(ctx):
    """Show agents and policies summary."""
    cli_obj = ctx.obj['cli']
    policies = cli_obj.get_policies()
    
    if policies:
        click.echo("📊 Policy Summary:")
        click.echo(f"   Version: {policies.get('version', 'N/A')}")
        click.echo(f"   Files: {len(policies.get('files', []))}")
        click.echo(f"   Agents: {len(policies.get('agents', []))}")
        click.echo(f"   Total Rules: {policies.get('total_rules', 0)}")
        
        files = policies.get('files', [])
        if files:
            click.echo(f"\n📁 Policy Files:")
            for file in sorted(files):
                click.echo(f"   • {file}")
        
        agents = policies.get('agents', [])
        if agents:
            click.echo(f"\n🤖 Agents:")
            for agent in sorted(agents):
                click.echo(f"   • {agent}")
    else:
        click.echo("No policy information available")


@cli.group()
def decisions():
    """Decision monitoring commands."""
    pass


@decisions.command()
@click.option('--limit', default=10, help='Number of recent decisions to show')
@click.option('--follow', '-f', is_flag=True, help='Follow decisions in real-time')
@click.pass_context
def tail(ctx, limit, follow):
    """Show recent policy decisions."""
    cli_obj = ctx.obj['cli']
    
    if follow:
        click.echo("📡 Following decisions (Ctrl+C to stop)...")
        last_seen = set()
        
        try:
            while True:
                decisions = cli_obj.get_decisions(limit=50)  # Get more for following
                
                # Show only new decisions
                new_decisions = []
                for decision in decisions:
                    decision_id = f"{decision.get('timestamp', '')}-{decision.get('agent_id', '')}-{decision.get('decision', '')}"
                    if decision_id not in last_seen:
                        new_decisions.append(decision)
                        last_seen.add(decision_id)
                
                # Keep last_seen manageable
                if len(last_seen) > 100:
                    last_seen = set(list(last_seen)[-50:])
                
                for decision in reversed(new_decisions):  # Show newest first
                    _print_decision(decision)
                
                time.sleep(2)  # Poll every 2 seconds
                
        except KeyboardInterrupt:
            click.echo("\n👋 Stopped following decisions")
    else:
        decisions = cli_obj.get_decisions(limit)
        
        if decisions:
            click.echo(f"📋 Last {len(decisions)} decisions:")
            for decision in decisions:
                _print_decision(decision)
        else:
            click.echo("No decisions found")


@decisions.command()
@click.option('--agent', help='Filter by agent ID')
@click.option('--decision', type=click.Choice(['allow', 'deny', 'pending_approval']), help='Filter by decision type')
@click.option('--limit', default=20, help='Number of decisions to show')
@click.pass_context
def filter(ctx, agent, decision, limit):
    """Filter and show policy decisions."""
    cli_obj = ctx.obj['cli']
    decisions = cli_obj.get_decisions(limit=100)  # Get more for filtering
    
    # Apply filters
    filtered = decisions
    if agent:
        filtered = [d for d in filtered if d.get('agent_id', '').lower() == agent.lower()]
    if decision:
        filtered = [d for d in filtered if d.get('decision', '') == decision]
    
    # Limit results
    filtered = filtered[:limit]
    
    if filtered:
        click.echo(f"🔍 Found {len(filtered)} matching decisions:")
        for dec in filtered:
            _print_decision(dec)
    else:
        click.echo("No matching decisions found")


@cli.group()
def test():
    """Testing commands."""
    pass


@test.command()
@click.argument('agent_id')
@click.argument('tool')
@click.argument('action')
@click.option('--params', help='JSON parameters for the tool call')
@click.option('--parent', help='Parent agent ID (for call chain testing)')
@click.pass_context
def call(ctx, agent_id, tool, action, params, parent):
    """Test a tool call through the gateway."""
    cli_obj = ctx.obj['cli']
    
    # Parse parameters
    try:
        params_dict = json.loads(params) if params else {}
    except json.JSONDecodeError as e:
        click.echo(f"❌ Invalid JSON parameters: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"🧪 Testing call: {agent_id} → {tool}/{action}")
    if parent:
        click.echo(f"   Parent: {parent}")
    if params_dict:
        click.echo(f"   Params: {json.dumps(params_dict, indent=2)}")
    
    result = cli_obj.test_tool_call(agent_id, tool, action, params_dict, parent)
    
    if "error" in result:
        click.echo(f"❌ Request failed: {result['error']}", err=True)
        sys.exit(1)
    
    status_code = result["status_code"]
    response = result["response"]
    
    # Format output based on status
    if status_code == 200:
        click.echo("✅ ALLOWED")
        click.echo(f"Response: {json.dumps(response, indent=2)}")
    elif status_code == 403:
        click.echo("🚫 DENIED")
        click.echo(f"Reason: {response.get('reason', 'Unknown')}")
    elif status_code == 202:
        click.echo("⏳ PENDING APPROVAL")
        click.echo(f"Approval ID: {response.get('approval_id', 'Unknown')}")
        click.echo(f"Reason: {response.get('reason', 'Unknown')}")
    else:
        click.echo(f"❓ Status: {status_code}")
        click.echo(f"Response: {json.dumps(response, indent=2)}")


def _print_decision(decision: Dict[str, Any]):
    """Print a formatted decision."""
    timestamp = decision.get('timestamp', 'Unknown')
    agent_id = decision.get('agent_id', 'Unknown')
    dec_type = decision.get('decision', 'Unknown')
    tool = decision.get('tool', 'Unknown')
    action = decision.get('action', 'Unknown')
    reason = decision.get('reason', 'No reason')
    
    # Format timestamp
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        time_str = dt.strftime('%H:%M:%S')
    except:
        time_str = timestamp
    
    # Choose emoji based on decision
    emoji = {
        'allow': '✅',
        'deny': '🚫',
        'pending_approval': '⏳'
    }.get(dec_type, '❓')
    
    click.echo(f"{emoji} [{time_str}] {agent_id} → {tool}/{action} ({dec_type})")
    if dec_type != 'allow':
        click.echo(f"    💬 {reason}")


if __name__ == '__main__':
    cli()
