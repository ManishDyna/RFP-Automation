"""
Enhanced Error Logger for RFP Automation
Provides clear, structured error reporting with failure point identification
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import os
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "INFO"           # Informational message
    SUCCESS = "SUCCESS"     # Successful operation
    WARNING = "WARNING"     # Warning - operation continued
    ERROR = "ERROR"         # Error - operation failed but automation continued
    CRITICAL = "CRITICAL"   # Critical error - automation stopped


class AutomationStep(Enum):
    """Standard automation steps"""
    INITIALIZATION = "1. Initialization"
    LOGIN = "2. Login"
    NAVIGATION = "3. Navigation"
    DATA_EXTRACTION = "4. Data Extraction"
    FORM_FILLING = "5. Form Filling"
    FILE_UPLOAD = "6. File Upload"
    FILE_DOWNLOAD = "7. File Download"
    VALIDATION = "8. Validation"
    SUBMISSION = "9. Submission"
    COMPLETION = "10. Completion"
    CLEANUP = "11. Cleanup"


def analyze_automation_logs(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze automation logs to identify where it stopped and what errors occurred.
    
    Returns:
        Dictionary with error analysis including:
        - last_successful_step: Last step that completed successfully
        - failure_point: Where the automation failed
        - error_summary: Clear description of what went wrong
        - error_details: Detailed error information
        - suggestions: Possible fixes
    """
    if not logs:
        return {
            "status": "NO_LOGS",
            "error_summary": "No automation logs available",
            "last_successful_step": None,
            "failure_point": None,
            "error_details": [],
            "suggestions": ["Check if automation was started"]
        }
    
    # Sort logs by timestamp (newest first)
    sorted_logs = sorted(logs, key=lambda x: x.get("Timestamp", ""), reverse=True)
    
    # Identify errors and warnings
    errors = []
    warnings = []
    last_success = None
    failure_point = None
    
    for log in reversed(sorted_logs):  # Process in chronological order
        status = log.get("automation_status", "").upper()
        action = log.get("Action", "")
        message = log.get("Message", "")
        category = log.get("Category", "")
        
        log_entry = {
            "timestamp": log.get("Timestamp"),
            "action": action,
            "status": status,
            "message": message,
            "category": category
        }
        
        # Track errors
        if status in ["FAIL", "FAILED", "ERROR", "CRITICAL"]:
            errors.append(log_entry)
            if not failure_point:
                failure_point = log_entry
        
        # Track warnings
        elif status in ["WARNING", "WARN"]:
            warnings.append(log_entry)
        
        # Track last successful operation
        elif status in ["SUCCESS", "COMPLETE", "COMPLETED"]:
            last_success = log_entry
    
    # Determine overall status
    if errors:
        status = "FAILED"
        error_summary = _generate_error_summary(failure_point, last_success, errors)
    elif warnings:
        status = "WARNING"
        error_summary = f"Automation completed with {len(warnings)} warnings"
    else:
        status = "SUCCESS"
        error_summary = "Automation completed successfully"
    
    # Generate suggestions
    suggestions = _generate_suggestions(failure_point, errors, warnings)
    
    # Create detailed error timeline
    error_timeline = _create_error_timeline(sorted_logs)
    
    return {
        "status": status,
        "error_summary": error_summary,
        "last_successful_step": last_success,
        "failure_point": failure_point,
        "total_errors": len(errors),
        "total_warnings": len(warnings),
        "error_details": errors,
        "warnings": warnings,
        "suggestions": suggestions,
        "error_timeline": error_timeline,
        "analysis_timestamp": datetime.utcnow().isoformat()
    }


def _generate_error_summary(failure_point: Optional[Dict], last_success: Optional[Dict], errors: List[Dict]) -> str:
    """Generate a clear, human-readable error summary"""
    if not failure_point:
        if errors:
            return f"Automation encountered {len(errors)} error(s) but failure point is unclear"
        return "Automation status unclear"
    
    action = failure_point.get("action", "Unknown action")
    message = failure_point.get("message", "No error message")
    
    summary_parts = []
    
    if last_success:
        last_action = last_success.get("action", "Unknown")
        summary_parts.append(f"Last successful step: {last_action}")
    
    summary_parts.append(f"Failed at: {action}")
    summary_parts.append(f"Error: {message}")
    
    return " | ".join(summary_parts)


def _generate_suggestions(failure_point: Optional[Dict], errors: List[Dict], warnings: List[Dict]) -> List[str]:
    """Generate actionable suggestions based on errors"""
    suggestions = []
    
    if not failure_point and not errors:
        return ["No errors detected"]
    
    if failure_point:
        message = failure_point.get("message", "").lower()
        action = failure_point.get("action", "").lower()
        
        # Timeout errors
        if "timeout" in message or "timed out" in message:
            suggestions.append("Timeout occurred - Check if the page/element is loading slowly")
            suggestions.append("   -> Increase timeout values in the script")
            suggestions.append("   -> Check network connectivity")

        # Element not found errors
        if "not found" in message or "could not find" in message or "selector" in message:
            suggestions.append("[Search] Element not found - The page structure may have changed")
            suggestions.append("   -> Verify the CSS/XPath selectors are correct")
            suggestions.append("   -> Check if the website was updated")

        # Login errors
        if "login" in action or "authentication" in message:
            suggestions.append("Login failed - Check credentials or session")
            suggestions.append("   -> Verify username and password are correct")
            suggestions.append("   -> Check if account is locked or requires password reset")
            suggestions.append("   -> Check if 2FA/MFA is required")

        # Upload errors
        if "upload" in action or "upload" in message:
            suggestions.append("File upload failed")
            suggestions.append("   -> Verify the file exists at the specified path")
            suggestions.append("   -> Check file size limits")
            suggestions.append("   -> Ensure file format is accepted")

        # Download errors
        if "download" in action or "download" in message:
            suggestions.append("[Download] File download failed")
            suggestions.append("   -> Check if download button is visible and enabled")
            suggestions.append("   -> Verify download folder permissions")
            suggestions.append("   -> Check if file already exists")

        # Click errors
        if "click" in action or "click" in message:
            suggestions.append("Click operation failed")
            suggestions.append("   -> Element may be hidden or disabled")
            suggestions.append("   -> Check if page finished loading")
            suggestions.append("   -> Try scrolling element into view first")

        # Network errors
        if "network" in message or "connection" in message:
            suggestions.append("Network error detected")
            suggestions.append("   -> Check internet connection")
            suggestions.append("   -> Verify the website is accessible")
            suggestions.append("   -> Check if proxy settings are correct")

    # Generic suggestions if no specific ones matched
    if not suggestions:
        suggestions.append("Review the error logs for details")
        suggestions.append("   -> Check the timestamp when error occurred")
        suggestions.append("   -> Look for patterns in repeated failures")
        suggestions.append("   -> Contact support if issue persists")
    
    return suggestions


def _create_error_timeline(logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create a step-by-step timeline showing progress and errors"""
    timeline = []
    
    for log in reversed(logs):  # Chronological order
        status = log.get("automation_status", "")
        action = log.get("Action", "")
        message = log.get("Message", "")
        timestamp = log.get("Timestamp", "")
        
        # Determine severity
        severity = _map_status_to_severity(status)
        
        # Add emoji indicators
        emoji = _get_status_emoji(severity)
        
        timeline.append({
            "timestamp": timestamp,
            "action": action,
            "status": status,
            "severity": severity.value,
            "message": message,
            "display": f"{emoji} [{status}] {action}: {message}"
        })
    
    return timeline


def _map_status_to_severity(status: str) -> ErrorSeverity:
    """Map automation status to error severity level"""
    status_upper = status.upper()
    
    if status_upper in ["FAIL", "FAILED", "ERROR", "CRITICAL"]:
        return ErrorSeverity.CRITICAL
    elif status_upper in ["WARNING", "WARN"]:
        return ErrorSeverity.WARNING
    elif status_upper in ["SUCCESS", "COMPLETE", "COMPLETED"]:
        return ErrorSeverity.SUCCESS
    else:
        return ErrorSeverity.INFO


def _get_status_emoji(severity: ErrorSeverity) -> str:
    """Get status indicator for severity"""
    emoji_map = {
        ErrorSeverity.INFO: "[INFO]",
        ErrorSeverity.SUCCESS: "[OK]",
        ErrorSeverity.WARNING: "[WARN]",
        ErrorSeverity.ERROR: "[ERROR]",
        ErrorSeverity.CRITICAL: "[CRITICAL]"
    }
    return emoji_map.get(severity, "->")


def create_enhanced_error_report(
    rfp_id: str,
    logs: List[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create an enhanced error report with clear failure identification.
    
    Args:
        rfp_id: The RFP identifier
        logs: List of automation logs
        context: Additional context information
    
    Returns:
        Enhanced error report with analysis
    """
    analysis = analyze_automation_logs(logs)
    
    report = {
        "rfp_id": rfp_id,
        "report_timestamp": datetime.utcnow().isoformat(),
        "context": context or {},
        "automation_status": analysis["status"],
        "error_summary": analysis["error_summary"],
        
        # Clear failure identification
        "failure_identification": {
            "last_successful_step": analysis.get("last_successful_step"),
            "failure_point": analysis.get("failure_point"),
            "total_errors": analysis.get("total_errors", 0),
            "total_warnings": analysis.get("total_warnings", 0)
        },
        
        # Detailed error information
        "error_details": analysis.get("error_details", []),
        "warnings": analysis.get("warnings", []),
        
        # Actionable suggestions
        "suggested_actions": analysis.get("suggestions", []),
        
        # Full timeline
        "error_timeline": analysis.get("error_timeline", []),
        
        # Raw logs for reference
        "raw_logs": logs,
        "total_log_entries": len(logs)
    }
    
    return report


def format_error_report_for_display(report: Dict[str, Any]) -> str:
    """Format error report as readable text"""
    lines = []
    
    lines.append("=" * 80)
    lines.append("AUTOMATION ERROR REPORT")
    lines.append("=" * 80)
    lines.append(f"\nRFP ID: {report['rfp_id']}")
    lines.append(f"Report Time: {report['report_timestamp']}")
    lines.append(f"Status: {report['automation_status']}")
    lines.append(f"\nSummary: {report['error_summary']}")
    
    # Failure identification
    failure = report['failure_identification']
    lines.append("\n" + "-" * 80)
    lines.append("FAILURE IDENTIFICATION")
    lines.append("-" * 80)
    
    if failure.get('last_successful_step'):
        last_step = failure['last_successful_step']
        lines.append(f"\n[OK] Last Successful Step:")
        lines.append(f"   Action: {last_step.get('action')}")
        lines.append(f"   Time: {last_step.get('timestamp')}")
        lines.append(f"   Message: {last_step.get('message')}")
    
    if failure.get('failure_point'):
        fail_point = failure['failure_point']
        lines.append(f"\n[CRITICAL] Failure Point:")
        lines.append(f"   Action: {fail_point.get('action')}")
        lines.append(f"   Time: {fail_point.get('timestamp')}")
        lines.append(f"   Status: {fail_point.get('status')}")
        lines.append(f"   Error Message: {fail_point.get('message')}")
    
    lines.append(f"\nError Count: {failure.get('total_errors', 0)}")
    lines.append(f"[WARN] Warning Count: {failure.get('total_warnings', 0)}")
    
    # Suggestions
    if report.get('suggested_actions'):
        lines.append("\n" + "-" * 80)
        lines.append("SUGGESTED ACTIONS")
        lines.append("-" * 80)
        for suggestion in report['suggested_actions']:
            lines.append(f"   {suggestion}")
    
    # Timeline (last 10 entries)
    timeline = report.get('error_timeline', [])
    if timeline:
        lines.append("\n" + "-" * 80)
        lines.append("ERROR TIMELINE (Last 10 Steps)")
        lines.append("-" * 80)
        for entry in timeline[-10:]:
            lines.append(f"\n{entry.get('display', '')}")
    
    lines.append("\n" + "=" * 80)
    
    return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    # Sample logs
    sample_logs = [
        {
            "Timestamp": "2025-11-26T15:06:49Z",
            "automation_status": "Click",
            "Action": "Submit",
            "Message": "Clicked 'Use selected lots'",
            "Category": "RFP"
        },
        {
            "Timestamp": "2025-11-26T15:06:35Z",
            "automation_status": "Upload",
            "Action": "Submit",
            "Message": "Imported Excel bidding from file",
            "Category": "RFP"
        },
        {
            "Timestamp": "2025-11-26T15:06:18Z",
            "automation_status": "Failed",
            "Action": "Submit",
            "Message": "Timeout waiting for element selector #submit_button",
            "Category": "RFP"
        }
    ]
    
    report = create_enhanced_error_report("TEST_RFP_001", sample_logs)
    print(format_error_report_for_display(report))







