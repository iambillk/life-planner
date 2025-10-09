# modules/admin_tools/ssh_scanner.py
"""
SSH Log Scanner Service
Parses MobaXterm SSH log files and imports them into the database

Version: 2.0.0
Created: 2025-10-08
Author: Billas + AI

Features:
- Scans NAS directory for .log files
- Parses MobaXterm log format WITH timestamps
- Extracts session metadata from filenames
- Parses log content for commands and timing
- Handles incremental updates (only new/modified files)
- Command classification and indexing
- Accurate output preview capture
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from models.base import db
from models.ssh_logs import SSHSession, SSHCommand, SSHScanLog


class MobaXtermLogParser:
    """Parser for MobaXterm log file format (with timestamps enabled)"""
    
    # Regex patterns for parsing
    FILENAME_PATTERN = r'\[(\w+)\s+([^\]]+)\]\s+\((\d{4}-\d{2}-\d{2}_\d{6})\)\s+(.+)\.log'
    TIMESTAMP_PATTERN = r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]'
    
    # Command line pattern: [timestamp] [user@host dir]# command
    COMMAND_PATTERN = r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]\s+\[(\w+)@([^\]]+)\s+([^\]]+)\][#$]\s+(.+)'
    
    MOBATERM_HEADER = r'MobaXterm\s+Professional\s+Edition\s+v([\d.]+)'
    SESSION_TO_PATTERN = r'SSH session to\s+([^\s]+)@([^\s]+)'
    AUTH_PATTERN = r'Authenticating with public key'
    LAST_LOGIN_PATTERN = r'Last login:\s+(.+?)(?:\r?\n|$)'
    SESSION_STOPPED = 'Session stopped'
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.filename = os.path.basename(file_path)
        self.file_size = os.path.getsize(file_path)
        self.file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        self.metadata = {}
        self.commands = []
        self.log_lines = []
    
    def parse(self) -> Dict:
        """
        Main parsing method
        Returns dict with all extracted data
        """
        # Parse filename for metadata
        self._parse_filename()
        
        # Read and parse log content
        self._read_log_file()
        self._parse_log_content()
        
        return {
            'metadata': self.metadata,
            'commands': self.commands,
            'file_info': {
                'path': self.file_path,
                'filename': self.filename,
                'size': self.file_size,
                'modified': self.file_modified
            }
        }
    
    def _parse_filename(self):
        """
        Parse filename to extract session metadata
        Format: [protocol user@host] (YYYY-MM-DD_HHMMSS) FriendlyName.log
        Example: [ssh root@208.76.81.107] (2025-10-08_114516) NetMon.log
        """
        match = re.search(self.FILENAME_PATTERN, self.filename)
        
        if match:
            protocol = match.group(1).lower()
            user_host = match.group(2)
            timestamp_str = match.group(3)
            friendly_name = match.group(4)
            
            # Parse user@host or just host
            if '@' in user_host:
                username, host = user_host.split('@', 1)
            else:
                username = None
                host = user_host
            
            # Parse timestamp
            session_start = datetime.strptime(timestamp_str, '%Y-%m-%d_%H%M%S')
            
            # Determine if host is IP or hostname
            ip_address = None
            hostname = None
            
            # Simple IP detection (matches xxx.xxx.xxx.xxx)
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                ip_address = host
                hostname = host  # Use IP as hostname too
            else:
                hostname = host
            
            self.metadata = {
                'protocol': protocol,
                'username': username,
                'hostname': hostname,
                'ip_address': ip_address,
                'friendly_name': friendly_name,
                'session_start': session_start,
            }
        else:
            # Fallback if filename doesn't match expected format
            self.metadata = {
                'protocol': 'unknown',
                'username': None,
                'hostname': 'unknown',
                'ip_address': None,
                'friendly_name': self.filename.replace('.log', ''),
                'session_start': self.file_modified,
            }
    
    def _read_log_file(self):
        """Read log file with encoding handling"""
        encodings = ['utf-8', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                with open(self.file_path, 'r', encoding=encoding, errors='replace') as f:
                    self.log_lines = f.readlines()
                break
            except Exception as e:
                if encoding == encodings[-1]:
                    raise Exception(f"Could not read file with any encoding: {e}")
    
    def _parse_log_content(self):
        """Parse log content for commands, timing, and session details"""
        
        commands = []
        session_end = None
        last_timestamp = None
        line_count = len(self.log_lines)
        
        # Look for MobaXterm version
        mobaterm_version = None
        authentication_method = None
        last_login_info = None
        exit_clean = False
        
        for i, line in enumerate(self.log_lines):
            line_stripped = line.strip()
            
            # Extract MobaXterm version
            if not mobaterm_version:
                version_match = re.search(self.MOBATERM_HEADER, line_stripped)
                if version_match:
                    mobaterm_version = version_match.group(1)
            
            # Check for authentication method
            if self.AUTH_PATTERN in line_stripped:
                authentication_method = 'public_key'
            
            # Extract last login info
            if not last_login_info and 'Last login:' in line_stripped:
                # Remove timestamp prefix if present
                clean_line = re.sub(self.TIMESTAMP_PATTERN, '', line_stripped).strip()
                login_match = re.search(self.LAST_LOGIN_PATTERN, clean_line)
                if login_match:
                    last_login_info = login_match.group(1).strip()
            
            # Look for command lines (timestamp + prompt + command)
            cmd_match = re.search(self.COMMAND_PATTERN, line_stripped)
            if cmd_match:
                timestamp_str = cmd_match.group(1)
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                last_timestamp = timestamp
                
                username = cmd_match.group(2)
                hostname = cmd_match.group(3)
                current_dir = cmd_match.group(4)
                command_text = cmd_match.group(5).strip()
                
                # Skip if empty command
                if not command_text:
                    continue
                
                # Check if user typed 'exit'
                if command_text.lower() in ['exit', 'logout', 'quit']:
                    exit_clean = True
                
                # Get output preview (next lines until next prompt or session end)
                output_lines = []
                for j in range(i + 1, min(i + 100, len(self.log_lines))):
                    next_line = self.log_lines[j].strip()
                    
                    # Stop if we hit another command prompt
                    if re.search(self.COMMAND_PATTERN, next_line):
                        break
                    
                    # Stop at session end
                    if self.SESSION_STOPPED in next_line:
                        break
                    
                    # Remove timestamp prefix from output line for cleaner preview
                    output_clean = re.sub(self.TIMESTAMP_PATTERN, '', next_line).strip()
                    
                    # Skip empty lines and system messages
                    if output_clean and not self._is_system_message(output_clean):
                        output_lines.append(output_clean)
                
                output_preview = '\n'.join(output_lines)[:1000]  # Limit to 1000 chars
                
                # Classify command
                command_type = SSHCommand.classify_command(command_text)
                
                commands.append({
                    'sequence_number': len(commands) + 1,
                    'timestamp': timestamp,
                    'command_text': command_text,
                    'output_preview': output_preview,
                    'command_type': command_type
                })
            
            # Check for session end
            if self.SESSION_STOPPED in line_stripped:
                if last_timestamp:
                    session_end = last_timestamp
        
        # Calculate session duration
        duration_seconds = None
        if session_end and self.metadata.get('session_start'):
            delta = session_end - self.metadata['session_start']
            duration_seconds = int(delta.total_seconds())
        
        # Update metadata
        self.metadata.update({
            'session_end': session_end,
            'duration_seconds': duration_seconds,
            'line_count': line_count,
            'command_count': len(commands),
            'mobaterm_version': mobaterm_version,
            'authentication_method': authentication_method or 'unknown',
            'last_login_info': last_login_info,
            'exit_clean': exit_clean,
            'status': 'completed' if session_end else 'incomplete'
        })
        
        self.commands = commands
    
    def _is_system_message(self, text: str) -> bool:
        """Determine if a line is a system message vs actual output"""
        system_indicators = [
            'MobaXterm',
            'SSH session to',
            'Direct SSH',
            'SSH compression',
            'X11-forwarding',
            'For more info',
            'Session stopped',
            'Press <Return>',
            'Press R to restart',
            'Press S to save',
            '=~=~=~=~=~',
            'Authenticating with',
        ]
        
        return any(indicator in text for indicator in system_indicators)


class SSHLogScanner:
    """Scans directory for SSH logs and imports them"""
    
    def __init__(self, scan_path: str):
        self.scan_path = scan_path
        self.stats = {
            'files_found': 0,
            'files_new': 0,
            'files_updated': 0,
            'files_skipped': 0,
            'files_error': 0
        }
        self.scan_log = None
    
    def scan(self) -> Dict:
        """
        Main scan method
        Returns statistics about the scan
        """
        # Create scan log entry
        self.scan_log = SSHScanLog(
            scan_path=self.scan_path,
            status='running'
        )
        db.session.add(self.scan_log)
        db.session.commit()
        
        start_time = datetime.utcnow()
        
        try:
            # Walk directory for .log files
            log_files = self._find_log_files()
            self.stats['files_found'] = len(log_files)
            
            # Process each file
            for file_path in log_files:
                try:
                    self._process_log_file(file_path)
                except Exception as e:
                    print(f"Error processing {file_path}: {e}")
                    self.stats['files_error'] += 1
            
            # Mark scan as completed
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.scan_log.scan_completed = end_time
            self.scan_log.duration_seconds = duration
            self.scan_log.status = 'completed'
            self.scan_log.files_found = self.stats['files_found']
            self.scan_log.files_new = self.stats['files_new']
            self.scan_log.files_updated = self.stats['files_updated']
            self.scan_log.files_skipped = self.stats['files_skipped']
            self.scan_log.files_error = self.stats['files_error']
            
            db.session.commit()
            
        except Exception as e:
            self.scan_log.status = 'error'
            self.scan_log.error_message = str(e)
            db.session.commit()
            raise
        
        return self.stats
    
    def _find_log_files(self) -> List[str]:
        """Recursively find all .log files in directory"""
        log_files = []
        
        if not os.path.exists(self.scan_path):
            raise FileNotFoundError(f"Scan path does not exist: {self.scan_path}")
        
        for root, dirs, files in os.walk(self.scan_path):
            for file in files:
                if file.endswith('.log'):
                    full_path = os.path.join(root, file)
                    log_files.append(full_path)
        
        return log_files
    
    def _process_log_file(self, file_path: str):
        """Process a single log file"""
        
        filename = os.path.basename(file_path)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # Check if file already exists in database
        existing_session = SSHSession.query.filter_by(filename=filename).first()
        
        if existing_session:
            # Check if file has been modified
            if existing_session.file_modified and existing_session.file_modified >= file_modified:
                self.stats['files_skipped'] += 1
                return
            
            # File was updated - re-import
            self._update_session(existing_session, file_path)
            self.stats['files_updated'] += 1
        else:
            # New file - import
            self._import_new_session(file_path)
            self.stats['files_new'] += 1
    
    def _import_new_session(self, file_path: str):
        """Import a new SSH session from log file"""
        
        # Parse the log file
        parser = MobaXtermLogParser(file_path)
        parsed_data = parser.parse()
        
        metadata = parsed_data['metadata']
        file_info = parsed_data['file_info']
        commands = parsed_data['commands']
        
        # Create session record
        session = SSHSession(
            filename=file_info['filename'],
            file_path=file_info['path'],
            file_size=file_info['size'],
            file_modified=file_info['modified'],
            protocol=metadata.get('protocol'),
            username=metadata.get('username'),
            hostname=metadata.get('hostname'),
            ip_address=metadata.get('ip_address'),
            friendly_name=metadata.get('friendly_name'),
            session_start=metadata.get('session_start'),
            session_end=metadata.get('session_end'),
            duration_seconds=metadata.get('duration_seconds'),
            authentication_method=metadata.get('authentication_method'),
            last_login_info=metadata.get('last_login_info'),
            mobaterm_version=metadata.get('mobaterm_version'),
            line_count=metadata.get('line_count'),
            command_count=metadata.get('command_count'),
            status=metadata.get('status'),
            exit_clean=metadata.get('exit_clean')
        )
        
        db.session.add(session)
        db.session.flush()  # Get session.id
        
        # Create command records
        for cmd_data in commands:
            command = SSHCommand(
                session_id=session.id,
                sequence_number=cmd_data['sequence_number'],
                timestamp=cmd_data['timestamp'],
                command_text=cmd_data['command_text'],
                output_preview=cmd_data['output_preview'],
                command_type=cmd_data['command_type']
            )
            db.session.add(command)
        
        db.session.commit()
    
    def _update_session(self, existing_session: SSHSession, file_path: str):
        """Re-import an updated log file"""
        
        # Delete old commands
        SSHCommand.query.filter_by(session_id=existing_session.id).delete()
        
        # Parse the updated file
        parser = MobaXtermLogParser(file_path)
        parsed_data = parser.parse()
        
        metadata = parsed_data['metadata']
        file_info = parsed_data['file_info']
        commands = parsed_data['commands']
        
        # Update session record
        existing_session.file_size = file_info['size']
        existing_session.file_modified = file_info['modified']
        existing_session.session_end = metadata.get('session_end')
        existing_session.duration_seconds = metadata.get('duration_seconds')
        existing_session.line_count = metadata.get('line_count')
        existing_session.command_count = metadata.get('command_count')
        existing_session.status = metadata.get('status')
        existing_session.exit_clean = metadata.get('exit_clean')
        existing_session.updated_at = datetime.utcnow()
        
        # Re-create command records
        for cmd_data in commands:
            command = SSHCommand(
                session_id=existing_session.id,
                sequence_number=cmd_data['sequence_number'],
                timestamp=cmd_data['timestamp'],
                command_text=cmd_data['command_text'],
                output_preview=cmd_data['output_preview'],
                command_type=cmd_data['command_type']
            )
            db.session.add(command)
        
        db.session.commit()


# Convenience functions

def scan_ssh_logs(nas_path: str) -> Dict:
    """
    Scan NAS directory for SSH logs and import them
    
    Args:
        nas_path: Path to directory containing SSH logs
        
    Returns:
        Dict with scan statistics
    """
    scanner = SSHLogScanner(nas_path)
    return scanner.scan()


def get_scan_history(limit: int = 10) -> List[SSHScanLog]:
    """Get recent scan history"""
    return SSHScanLog.query.order_by(SSHScanLog.scan_started.desc()).limit(limit).all()


def parse_single_log(file_path: str) -> Dict:
    """Parse a single log file without importing to database"""
    parser = MobaXtermLogParser(file_path)
    return parser.parse()