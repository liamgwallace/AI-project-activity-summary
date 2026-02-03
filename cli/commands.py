"""
CLI commands for testing and managing the Personal Activity Intelligence System.
"""

import argparse
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import load_settings, get_settings
from storage.database import Database


def test_github(args):
    """Test GitHub API connection and fetch sample data."""
    print("Testing GitHub integration...")
    settings = get_settings()
    
    if not settings.github.token:
        print("Error: PAIS_GITHUB_TOKEN not set in environment")
        return 1
    
    try:
        from github import Github
        
        g = Github(settings.github.token)
        user = g.get_user()
        print(f"Authenticated as: {user.login}")
        print(f"GitHub name: {user.name or 'N/A'}")
        
        # Test recent events
        print("\nRecent events (last 24 hours):")
        since = datetime.now() - timedelta(days=1)
        
        events_found = 0
        for repo in user.get_repos():
            if events_found >= 5:
                break
            
            try:
                for commit in repo.get_commits(since=since):
                    if events_found >= 5:
                        break
                    print(f"  - {repo.name}: {commit.sha[:7]} - {commit.commit.message[:50]}")
                    events_found += 1
            except Exception as e:
                continue
        
        if events_found == 0:
            print("  No recent commits found")
        
        # Store in database if requested
        if args.store and events_found > 0:
            db = Database(settings.database.path)
            print(f"\nWould store {events_found} events to database")
        
        print("\nGitHub test completed successfully!")
        return 0
        
    except ImportError:
        print("Error: PyGithub not installed. Run: pip install PyGithub")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def test_gmail(args):
    """Test Gmail API connection and fetch sample emails."""
    print("Testing Gmail integration...")
    settings = get_settings()
    
    if not settings.gmail.credentials_path:
        print("Error: PAIS_GMAIL_CREDENTIALS_PATH not set")
        return 1
    
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
        
        creds = None
        token_path = settings.gmail.token_path
        
        if Path(token_path).exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(settings.gmail.credentials_path).exists():
                    print(f"Error: Credentials file not found: {settings.gmail.credentials_path}")
                    return 1
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.gmail.credentials_path,
                    ["https://www.googleapis.com/auth/gmail.readonly"]
                )
                creds = flow.run_local_server(port=0)
            
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
        
        service = build("gmail", "v1", credentials=creds)
        
        # Get recent messages
        results = service.users().messages().list(userId="me", maxResults=5).execute()
        messages = results.get("messages", [])
        
        print(f"Found {len(messages)} recent messages")
        
        for msg in messages[:3]:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = msg_data["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            from_addr = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            print(f"  - {from_addr}: {subject[:60]}")
        
        print("\nGmail test completed successfully!")
        return 0
        
    except ImportError:
        print("Error: Google API libraries not installed")
        print("Run: pip install google-auth google-auth-oauthlib google-api-python-client")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def test_calendar(args):
    """Test Google Calendar API connection and fetch events."""
    print("Testing Calendar integration...")
    settings = get_settings()
    
    if not settings.calendar.credentials_path:
        print("Error: PAIS_CALENDAR_CREDENTIALS_PATH not set")
        return 1
    
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
        
        creds = None
        token_path = settings.calendar.token_path
        
        if Path(token_path).exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not Path(settings.calendar.credentials_path).exists():
                    print(f"Error: Credentials file not found: {settings.calendar.credentials_path}")
                    return 1
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.calendar.credentials_path,
                    ["https://www.googleapis.com/auth/calendar.readonly"]
                )
                creds = flow.run_local_server(port=0)
            
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
        
        service = build("calendar", "v3", credentials=creds)
        
        # Get events from last 7 days
        now = datetime.now()
        time_min = (now - timedelta(days=7)).isoformat() + "Z"
        time_max = now.isoformat() + "Z"
        
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        ).execute()
        
        events = events_result.get("items", [])
        print(f"Found {len(events)} events in the last 7 days")
        
        for event in events[:5]:
            start = event["start"].get("dateTime", event["start"].get("date"))
            summary = event.get("summary", "No Title")
            print(f"  - {start}: {summary}")
        
        print("\nCalendar test completed successfully!")
        return 0
        
    except ImportError:
        print("Error: Google API libraries not installed")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def test_db(args):
    """Test database connection and operations."""
    print("Testing database...")
    settings = get_settings()
    
    try:
        db = Database(settings.database.path)
        
        # Test insert
        event_id = db.insert_event(
            source="test",
            event_type="test_event",
            raw_data=json.dumps({"test": True}),
            event_time=datetime.now().isoformat()
        )
        print(f"Inserted test event with ID: {event_id}")
        
        # Test query
        since = datetime.now() - timedelta(days=1)
        events = db.get_events_since(since)
        print(f"Found {len(events)} events since yesterday")
        
        # Test project
        project_id, created = db.get_or_create_project(
            name="TestProject",
            description="A test project",
            keywords="test,example"
        )
        print(f"Project {'created' if created else 'found'} with ID: {project_id}")
        
        # Test activity
        activity_id = db.insert_activity(
            timestamp=datetime.now().isoformat(),
            project_name="TestProject",
            activity_type="test",
            description="Test activity",
        )
        print(f"Inserted activity with ID: {activity_id}")
        
        # Test stats
        stats = db.get_token_stats(days=30)
        print(f"\nDatabase stats: {stats['total_operations']} operations recorded")
        
        print("\nDatabase test completed successfully!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def test_ai(args):
    """Test AI model connectivity."""
    print("Testing AI integration...")
    settings = get_settings()
    
    if not settings.openai.api_key:
        print("Error: PAIS_OPENAI_API_KEY not set")
        return 1
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        
        model = args.model or settings.openai.model
        print(f"Using model: {model}")
        print(f"API key (first 10 chars): {settings.openai.api_key[:10]}...")
        
        llm = ChatOpenAI(
            model=model,
            temperature=settings.openai.temperature,
            api_key=settings.openai.api_key,
        )
        
        messages = [HumanMessage(content="Say 'AI test successful' in 5 words or less.")]
        response = llm.invoke(messages)
        
        print(f"Full response: {response}")
        print(f"Response content: '{response.content}'")
        print(f"\nAI test completed!")
        return 0
        
    except ImportError:
        print("Error: LangChain not installed")
        print("Run: pip install langchain langchain-openai")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


def collect_all(args):
    """Collect data from all sources."""
    print("Collecting data from all sources...")
    
    # Run all collectors
    result = 0
    
    if not args.skip_github:
        print("\n--- GitHub ---")
        result |= test_github(argparse.Namespace(store=True))
    
    if not args.skip_gmail:
        print("\n--- Gmail ---")
        result |= test_gmail(argparse.Namespace())
    
    if not args.skip_calendar:
        print("\n--- Calendar ---")
        result |= test_calendar(argparse.Namespace())
    
    print("\nCollection completed!")
    return result


def process_now(args):
    """Process unprocessed events immediately."""
    print("Processing unprocessed events...")
    settings = get_settings()
    
    try:
        db = Database(settings.database.path)
        
        events = db.get_unprocessed_events(limit=args.limit)
        
        if not events:
            print("No unprocessed events found")
            return 0
        
        print(f"Found {len(events)} events to process")
        
        # Create batch
        batch_id = db.create_batch(
            total_events=len(events),
            model_used=settings.openai.model
        )
        print(f"Created processing batch: {batch_id}")
        
        # Process events (simplified)
        processed = 0
        event_ids = []
        
        for event in events:
            # Simplified processing - in production, this would use AI
            print(f"  Processing: {event.source} - {event.event_type}")
            event_ids.append(event.id)
            processed += 1
        
        # Mark as processed
        db.mark_events_processed(event_ids)
        
        # Complete batch
        db.complete_batch(
            batch_id=batch_id,
            processed_count=processed,
            tokens_used=0
        )
        
        print(f"\nProcessed {processed} events successfully!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def show_events(args):
    """Show recent events from the database."""
    print("Showing recent events...")
    settings = get_settings()
    
    try:
        db = Database(settings.database.path)
        
        since = datetime.now() - timedelta(days=args.days)
        events = db.get_events_since(since)
        
        if not events:
            print("No events found")
            return 0
        
        print(f"\nFound {len(events)} events in the last {args.days} days:\n")
        
        for event in events[:args.limit]:
            status = "[P]" if event.processed else "[U]"
            print(f"{status} {event.id}: {event.source}/{event.event_type}")
            print(f"   Time: {event.event_time}")
            
            if args.verbose:
                data = json.loads(event.raw_data) if event.raw_data else {}
                print(f"   Data: {json.dumps(data, indent=2)[:200]}")
            print()
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def show_stats(args):
    """Show system statistics."""
    print("System Statistics")
    print("=" * 50)
    
    settings = get_settings()
    
    try:
        db = Database(settings.database.path)
        
        # Token stats
        stats = db.get_token_stats(days=args.days)
        
        print(f"\nPeriod: Last {stats['period_days']} days")
        print(f"Total Operations: {stats['total_operations']}")
        print(f"Total Tokens: {stats['total_tokens']:,}")
        print(f"  - Input: {stats['total_input_tokens']:,}")
        print(f"  - Output: {stats['total_output_tokens']:,}")
        print(f"Estimated Cost: ${stats['total_cost']:.4f}")
        
        if stats['by_model']:
            print("\nBy Model:")
            for model, model_stats in stats['by_model'].items():
                print(f"  {model}:")
                print(f"    Tokens: {model_stats['total_tokens']:,}")
                print(f"    Cost: ${model_stats['cost']:.4f}")
        
        if stats['batches']['total']:
            print(f"\nProcessing Batches:")
            print(f"  Total: {stats['batches']['total']}")
            print(f"  Completed: {stats['batches']['completed']}")
            print(f"  Failed: {stats['batches']['failed']}")
        
        # Event stats
        since = datetime.now() - timedelta(days=args.days)
        events = db.get_events_since(since)
        unprocessed = [e for e in events if not e.processed]
        
        print(f"\nEvents:")
        print(f"  Total: {len(events)}")
        print(f"  Unprocessed: {len(unprocessed)}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def generate_logs(args):
    """Generate activity logs/report."""
    print("Generating activity logs...")
    settings = get_settings()
    
    try:
        db = Database(settings.database.path)
        
        # Get activities for the period
        since = datetime.now() - timedelta(days=args.days)
        activities = db.get_activities_for_period(
            start=since,
            end=datetime.now(),
            project_name=args.project if args.project else None
        )
        
        if not activities:
            print("No activities found for the specified period")
            return 0
        
        print(f"\nFound {len(activities)} activities:\n")
        
        for activity in activities:
            print(f"[{activity.timestamp}] {activity.project_name}")
            print(f"  Type: {activity.activity_type}")
            print(f"  {activity.description}")
            print()
        
        # Save to file if requested
        if args.output:
            log_data = {
                "generated_at": datetime.now().isoformat(),
                "period_days": args.days,
                "activities": [
                    {
                        "timestamp": a.timestamp,
                        "project": a.project_name,
                        "type": a.activity_type,
                        "description": a.description,
                    }
                    for a in activities
                ]
            }
            
            with open(args.output, "w") as f:
                json.dump(log_data, f, indent=2)
            print(f"Saved to: {args.output}")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def test_obsidian(args):
    """Test Obsidian vault write/read functionality."""
    print("Testing Obsidian vault integration...")
    settings = get_settings()
    
    try:
        from storage.obsidian_writer import ObsidianWriter
        
        # Determine vault paths
        project_vault = settings.obsidian.project_vault or str(Path(settings.data_dir) / "project-vault")
        personal_vault = settings.obsidian.personal_vault or str(Path(settings.data_dir) / "personal-vault")
        
        print(f"\nProject vault: {project_vault}")
        print(f"Personal vault: {personal_vault}")
        
        # Initialize writer
        writer = ObsidianWriter(
            project_vault=str(project_vault),
            personal_vault=str(personal_vault)
        )
        
        # Test 1: Write test activity log
        print("\n1. Testing activity log write...")
        test_activities = [
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "description": "Test activity - setting up Obsidian integration",
                "type": "test",
                "technologies": ["Python", "Obsidian", "PAIS"]
            },
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "description": "Another test entry to verify multiple activities",
                "type": "documentation",
                "technologies": ["Markdown"]
            }
        ]
        
        log_path = writer.write_activity_log("TestProject", test_activities)
        print(f"   ✓ Activity log written to: {log_path}")
        
        # Verify file exists and is readable
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8")
            print(f"   ✓ File verified ({len(content)} bytes)")
        
        # Test 2: Write personal activity log
        print("\n2. Testing personal activity log write...")
        personal_activities = [
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "description": "Testing personal vault integration",
                "type": "learning"
            }
        ]
        
        personal_log_path = writer.write_personal_activity_log(personal_activities)
        print(f"   ✓ Personal activity log written to: {personal_log_path}")
        
        # Test 3: Write README update
        print("\n3. Testing README update...")
        test_summary = """This is a test weekly summary generated by PAIS.

### Activities
- Set up Obsidian vault integration
- Tested markdown file generation
- Verified vault paths are working correctly

### Notes
Everything appears to be working as expected!"""
        
        readme_path = writer.update_project_readme("TestProject", test_summary)
        print(f"   ✓ README updated at: {readme_path}")
        
        # Test 4: Write tweet drafts
        print("\n4. Testing tweet drafts write...")
        test_tweets = [
            {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "content": "Just set up my PAIS integration with Obsidian! 🚀 Now all my project activities are automatically documented. #Productivity #Obsidian",
                "project_name": "TestProject",
                "posted": False
            }
        ]
        
        drafts_path = writer.write_tweet_drafts(test_tweets)
        print(f"   ✓ Tweet drafts written to: {drafts_path}")
        
        # Test 5: Verify all files exist
        print("\n5. Verifying all test files...")
        test_files = [log_path, personal_log_path, readme_path, drafts_path]
        all_exist = all(f.exists() for f in test_files)
        
        if all_exist:
            print("   ✓ All test files created successfully!")
            print(f"\n   Total files created: {len(test_files)}")
            print(f"   Project vault: {project_vault}")
            print(f"   Personal vault: {personal_vault}")
        else:
            print("   ✗ Some files are missing!")
            return 1
        
        # Test 6: AI-generated content (if AI is configured)
        if settings.openai.api_key and args.use_ai:
            print("\n6. Testing AI-generated content...")
            try:
                from langchain_openai import ChatOpenAI
                from langchain_core.messages import HumanMessage
                
                llm = ChatOpenAI(
                    model=settings.openai.model,
                    temperature=0.7,
                    api_key=settings.openai.api_key,
                )
                
                messages = [HumanMessage(content="Write a short 3-sentence test note about testing Obsidian vault integration.")]
                response = llm.invoke(messages)
                
                ai_content = response.content
                
                # Write AI-generated content
                ai_activities = [
                    {
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "description": ai_content,
                        "type": "ai-generated",
                        "technologies": ["AI", "LangChain"]
                    }
                ]
                
                ai_log_path = writer.write_activity_log("AIGeneratedTest", ai_activities)
                print(f"   ✓ AI-generated content written to: {ai_log_path}")
                
            except Exception as e:
                print(f"   ⚠ AI test skipped (error: {e})")
        
        print("\n" + "=" * 50)
        print("Obsidian vault test completed successfully! ✓")
        print("=" * 50)
        print("\nTest files created:")
        print(f"  - {log_path}")
        print(f"  - {personal_log_path}")
        print(f"  - {readme_path}")
        print(f"  - {drafts_path}")
        
        if args.keep:
            print("\nTest files retained (use --clean to remove them)")
        else:
            print("\nCleaning up test files...")
            import shutil
            test_project_folder = Path(project_vault) / "test-project"
            if test_project_folder.exists():
                shutil.rmtree(test_project_folder)
                print("  ✓ Test files removed")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Personal Activity Intelligence System CLI",
        prog="pais"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # test-github command
    github_parser = subparsers.add_parser("test-github", help="Test GitHub integration")
    github_parser.add_argument("--store", action="store_true", help="Store results in database")
    
    # test-gmail command
    subparsers.add_parser("test-gmail", help="Test Gmail integration")
    
    # test-calendar command
    subparsers.add_parser("test-calendar", help="Test Calendar integration")
    
    # test-db command
    subparsers.add_parser("test-db", help="Test database operations")
    
    # test-ai command
    ai_parser = subparsers.add_parser("test-ai", help="Test AI integration")
    ai_parser.add_argument("--model", help="Model to use (e.g., gpt-4o-mini, openai/gpt-4o)")
    
    # test-obsidian command
    obsidian_parser = subparsers.add_parser("test-obsidian", help="Test Obsidian vault integration")
    obsidian_parser.add_argument("--use-ai", action="store_true", help="Generate AI content for testing")
    obsidian_parser.add_argument("--keep", action="store_true", help="Keep test files (don't clean up)")
    
    # collect-all command
    collect_parser = subparsers.add_parser("collect-all", help="Collect data from all sources")
    collect_parser.add_argument("--skip-github", action="store_true", help="Skip GitHub")
    collect_parser.add_argument("--skip-gmail", action="store_true", help="Skip Gmail")
    collect_parser.add_argument("--skip-calendar", action="store_true", help="Skip Calendar")
    
    # process-now command
    process_parser = subparsers.add_parser("process-now", help="Process unprocessed events")
    process_parser.add_argument("--limit", type=int, default=100, help="Max events to process")
    
    # show-events command
    events_parser = subparsers.add_parser("show-events", help="Show recent events")
    events_parser.add_argument("--days", type=int, default=7, help="Days to look back")
    events_parser.add_argument("--limit", type=int, default=20, help="Max events to show")
    events_parser.add_argument("--verbose", "-v", action="store_true", help="Show full data")
    
    # show-stats command
    stats_parser = subparsers.add_parser("show-stats", help="Show system statistics")
    stats_parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    
    # generate-logs command
    logs_parser = subparsers.add_parser("generate-logs", help="Generate activity logs")
    logs_parser.add_argument("--days", type=int, default=7, help="Days to include")
    logs_parser.add_argument("--project", help="Filter by project name")
    logs_parser.add_argument("--output", "-o", help="Output file path")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Map commands to functions
    commands = {
        "test-github": test_github,
        "test-gmail": test_gmail,
        "test-calendar": test_calendar,
        "test-db": test_db,
        "test-ai": test_ai,
        "test-obsidian": test_obsidian,
        "collect-all": collect_all,
        "process-now": process_now,
        "show-events": show_events,
        "show-stats": show_stats,
        "generate-logs": generate_logs,
    }
    
    # Load settings before running command
    load_settings()
    
    # Execute command
    if args.command in commands:
        return commands[args.command](args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
