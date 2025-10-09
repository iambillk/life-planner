# modules/admin_tools/live_routes.py
"""
Live Monitoring Tool Routes
Real-time streaming tools for continuous monitoring
Version: 1.0.1 - FIXED
Created: 2025-01-10
"""

from flask import render_template, request, redirect, url_for, flash, Response, jsonify, current_app
from datetime import datetime, timedelta
import subprocess
import threading
import queue
import time
import re
import signal

from models.base import db
from models.admin_tools import LiveToolSession
from . import admin_tools_bp

# Global storage for active subprocess and their output queues
# Format: {session_id: {'process': Popen, 'queue': Queue, 'stats': dict}}
ACTIVE_SESSIONS = {}
SESSION_LOCK = threading.Lock()


def parse_ping_line(line):
    """
    Parse a single ping output line and extract statistics
    Returns: (packets_sent, packets_received) or (0, 0) if not a ping line
    """
    # Windows ping format: "Reply from 192.168.1.1: bytes=32 time=1ms TTL=64"
    # Or: "Request timed out."
    
    if "Reply from" in line or "bytes=" in line:
        return (1, 1)  # Sent 1, received 1
    elif "Request timed out" in line or "timed out" in line.lower():
        return (1, 0)  # Sent 1, received 0
    elif "Destination host unreachable" in line:
        return (1, 0)  # Sent 1, received 0
    
    return (0, 0)  # Not a ping result line


def stream_process_output(process, output_queue, session_id):
    """
    Background thread that reads subprocess output line by line
    and puts it into a queue for SSE streaming
    """
    try:
        for line in iter(process.stdout.readline, b''):
            if not line:
                break
            
            decoded_line = line.decode('utf-8', errors='replace').strip()
            
            # Parse ping statistics
            sent, received = parse_ping_line(decoded_line)
            
            # Put line and stats into queue
            output_queue.put({
                'type': 'output',
                'line': decoded_line,
                'sent': sent,
                'received': received
            })
        
        # Process finished
        output_queue.put({'type': 'finished'})
        
    except Exception as e:
        output_queue.put({'type': 'error', 'message': str(e)})


# ==================== LIVE MONITORING DASHBOARD ====================

@admin_tools_bp.route('/live')
def live_dashboard():
    """Live monitoring tools dashboard"""
    
    # Cleanup old orphaned sessions
    LiveToolSession.cleanup_orphaned_sessions(timeout_minutes=60)
    
    # Get active sessions
    active_sessions = LiveToolSession.get_active_sessions()
    
    # Get recent completed sessions
    recent_sessions = LiveToolSession.query.filter(
        LiveToolSession.status != 'running'
    ).order_by(LiveToolSession.started_at.desc()).limit(10).all()
    
    return render_template('admin_tools/live_dashboard.html',
                         active_sessions=active_sessions,
                         recent_sessions=recent_sessions,
                         active='admin_tools')


# ==================== CONTINUOUS PING ====================

@admin_tools_bp.route('/live/continuous-ping', methods=['GET', 'POST'])
def continuous_ping():
    """Start a continuous ping monitoring session"""
    
    if request.method == 'POST':
        target = request.form.get('target', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not target:
            flash('Target is required', 'warning')
            return redirect(url_for('admin_tools.continuous_ping'))
        
        # Create session record
        session = LiveToolSession(
            tool_name='continuous_ping',
            target=target,
            notes=notes,
            status='running'
        )
        db.session.add(session)
        db.session.commit()
        
        # Redirect to live terminal view
        return redirect(url_for('admin_tools.live_terminal', session_id=session.id))
    
    # GET - show form
    return render_template('admin_tools/continuous_ping_form.html',
                         active='admin_tools')


@admin_tools_bp.route('/live/terminal/<int:session_id>')
def live_terminal(session_id):
    """Full-page terminal view for active monitoring session"""
    
    session = LiveToolSession.query.get_or_404(session_id)
    
    return render_template('admin_tools/live_terminal.html',
                         session=session,
                         active='admin_tools')


@admin_tools_bp.route('/live/start/<int:session_id>')
def start_session(session_id):
    """Start the actual subprocess for a session"""
    
    session = LiveToolSession.query.get_or_404(session_id)
    
    if session.status != 'running':
        return jsonify({'error': 'Session is not in running state'}), 400
    
    with SESSION_LOCK:
        # Check if already started
        if session_id in ACTIVE_SESSIONS:
            return jsonify({'error': 'Session already started'}), 400
        
        try:
            # Start subprocess
            # Windows: ping -t target
            cmd = ['ping', '-t', session.target]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,  # Unbuffered - FIXED
                universal_newlines=False
            )
            
            # Create output queue
            output_queue = queue.Queue(maxsize=1000)
            
            # Start background thread to read output
            thread = threading.Thread(
                target=stream_process_output,
                args=(process, output_queue, session_id),
                daemon=True
            )
            thread.start()
            
            # Store session info
            ACTIVE_SESSIONS[session_id] = {
                'process': process,
                'queue': output_queue,
                'thread': thread,
                'stats': {'sent': 0, 'received': 0}
            }
            
            # Update session with PID
            session.process_pid = process.pid
            db.session.commit()
            
            return jsonify({'success': True, 'pid': process.pid})
            
        except Exception as e:
            session.status = 'failed'
            db.session.commit()
            return jsonify({'error': str(e)}), 500


@admin_tools_bp.route('/live/stream/<int:session_id>')
def stream_session(session_id):
    """Server-Sent Events endpoint for streaming output"""
    
    # Get session data OUTSIDE the generator to avoid context issues
    session = LiveToolSession.query.get_or_404(session_id)
    target = session.target
    
    def generate():
        """Generator function for SSE"""
        
        # Wait a moment for session to start
        time.sleep(0.5)
        
        session_info = ACTIVE_SESSIONS.get(session_id)
        
        if not session_info:
            yield f"data: {{'type': 'error', 'message': 'Session not started'}}\n\n"
            return
        
        output_queue = session_info['queue']
        stats = session_info['stats']
        
        # Send initial message
        yield f"data: {{'type': 'started', 'target': '{target}'}}\n\n"
        
        # Stream output
        while True:
            try:
                # Get from queue with timeout
                msg = output_queue.get(timeout=1.0)
                
                if msg['type'] == 'output':
                    # Update stats
                    stats['sent'] += msg['sent']
                    stats['received'] += msg['received']
                    
                    # Send line to browser
                    import json
                    data = {
                        'type': 'output',
                        'line': msg['line'],
                        'sent': stats['sent'],
                        'received': stats['received']
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                
                elif msg['type'] == 'finished':
                    yield f"data: {{'type': 'finished'}}\n\n"
                    break
                
                elif msg['type'] == 'error':
                    import json
                    yield f"data: {json.dumps({'type': 'error', 'message': msg['message']})}\n\n"
                    break
                    
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield f": heartbeat\n\n"
                
                # Check if session was stopped externally - FIXED with app_context
                try:
                    with current_app.app_context():
                        fresh_session = LiveToolSession.query.get(session_id)
                        if fresh_session and fresh_session.status != 'running':
                            yield f"data: {{'type': 'stopped'}}\n\n"
                            break
                except:
                    # If we can't check, just continue
                    pass
    
    return Response(generate(), mimetype='text/event-stream')


@admin_tools_bp.route('/live/stop/<int:session_id>', methods=['POST'])
def stop_session(session_id):
    """Stop an active monitoring session"""
    
    session = LiveToolSession.query.get_or_404(session_id)
    
    with SESSION_LOCK:
        session_info = ACTIVE_SESSIONS.get(session_id)
        
        if session_info:
            process = session_info['process']
            stats = session_info['stats']
            
            # Kill the subprocess
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
            
            # Update session record
            session.stopped_at = datetime.utcnow()
            session.status = 'stopped'
            session.packets_sent = stats['sent']
            session.packets_received = stats['received']
            
            if stats['sent'] > 0:
                loss = ((stats['sent'] - stats['received']) / stats['sent']) * 100
                session.packet_loss_pct = round(loss, 2)
            
            delta = session.stopped_at - session.started_at
            session.duration_seconds = int(delta.total_seconds())
            
            # Clean up
            del ACTIVE_SESSIONS[session_id]
        else:
            # Session not in memory (maybe server restarted)
            session.status = 'stopped'
            session.stopped_at = datetime.utcnow()
            if not session.duration_seconds and session.started_at:
                delta = session.stopped_at - session.started_at
                session.duration_seconds = int(delta.total_seconds())
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'packets_sent': session.packets_sent,
            'packets_received': session.packets_received,
            'packet_loss_pct': session.packet_loss_pct,
            'duration': session.formatted_duration
        })


@admin_tools_bp.route('/live/session/<int:session_id>')
def view_live_session(session_id):
    """View details of a completed live session"""
    
    session = LiveToolSession.query.get_or_404(session_id)
    
    return render_template('admin_tools/live_session_detail.html',
                         session=session,
                         active='admin_tools')


@admin_tools_bp.route('/live/sessions')
def live_sessions_history():
    """View history of all live monitoring sessions"""
    
    # Cleanup orphaned first
    LiveToolSession.cleanup_orphaned_sessions()
    
    sessions = LiveToolSession.get_recent_sessions(limit=100)
    
    # Calculate stats
    total_sessions = len(sessions)
    active_now = sum(1 for s in sessions if s.status == 'running')
    completed = sum(1 for s in sessions if s.status == 'stopped')
    
    stats = {
        'total': total_sessions,
        'active': active_now,
        'completed': completed,
    }
    
    return render_template('admin_tools/live_sessions_history.html',
                         sessions=sessions,
                         stats=stats,
                         active='admin_tools')