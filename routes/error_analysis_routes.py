"""
API Routes for Enhanced Error Analysis
Provides endpoints to analyze automation logs and generate error reports
"""

from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from helpers.enhanced_error_logger import (
    create_enhanced_error_report,
    format_error_report_for_display,
    analyze_automation_logs
)
from config.config import AUTOMATION_LOG_TABLE_API, AUTOMATION_LOG_TABLE_LOGICAL
from helpers.core_helper import DATAVERSE

router = APIRouter(prefix="/api/error-analysis", tags=["Error Analysis"])


class LogEntry(BaseModel):
    """Single log entry model"""
    Timestamp: str
    automation_status: str
    Action: str
    Message: str
    Category: Optional[str] = "RFP"
    RFP_ID: Optional[str] = ""


class AnalyzeLogsRequest(BaseModel):
    """Request model for analyzing logs"""
    rfp_id: str
    logs: List[Dict[str, Any]]
    context: Optional[Dict[str, Any]] = None


class AnalyzeRFPRequest(BaseModel):
    """Request model for analyzing RFP by ID"""
    rfp_id: str
    context: Optional[Dict[str, Any]] = None


@router.post("/analyze-logs")
async def analyze_logs_endpoint(request: AnalyzeLogsRequest):
    """
    Analyze automation logs and get enhanced error report.
    
    Example Request:
    ```json
    {
        "rfp_id": "Aramco_4203233223_CABLE",
        "logs": [
            {
                "Timestamp": "2025-11-26T15:06:49Z",
                "automation_status": "Success",
                "Action": "Submit",
                "Message": "Clicked button",
                "Category": "RFP"
            },
            {
                "Timestamp": "2025-11-26T15:07:00Z",
                "automation_status": "Failed",
                "Action": "Submit",
                "Message": "Timeout waiting for element",
                "Category": "RFP"
            }
        ],
        "context": {
            "automation": "submit_rfp",
            "company": "Aramco"
        }
    }
    ```
    """
    try:
        report = create_enhanced_error_report(
            rfp_id=request.rfp_id,
            logs=request.logs,
            context=request.context
        )
        
        return JSONResponse(
            status_code=200,
            content=report
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-logs/formatted")
async def analyze_logs_formatted_endpoint(request: AnalyzeLogsRequest):
    """
    Get enhanced error report in human-readable text format.
    Returns plain text that can be displayed in console or email.
    """
    try:
        report = create_enhanced_error_report(
            rfp_id=request.rfp_id,
            logs=request.logs,
            context=request.context
        )
        
        formatted_text = format_error_report_for_display(report)
        
        return PlainTextResponse(
            content=formatted_text,
            status_code=200
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-rfp")
async def analyze_rfp_by_id_endpoint(request: AnalyzeRFPRequest):
    """
    Analyze RFP by ID - fetches logs from Dataverse and analyzes them.
    
    Example Request:
    ```json
    {
        "rfp_id": "Aramco_4203233223_CABLE, POWER, 5KV THROUGH 35 KV",
        "context": {
            "automation": "submit_rfp",
            "company": "Aramco e-Marketplace"
        }
    }
    ```
    """
    try:
        # Fetch logs from Dataverse
        logs = []
        try:
            rows = DATAVERSE.get_rows_from_dataverse(
                table_api_name=AUTOMATION_LOG_TABLE_API,
                filter_by={"RFP_ID": request.rfp_id},
                select_columns=["RunID", "Timestamp", "Category", "Action", "automation_status", "Message", "RFP_ID"],
                top=500,
                order_by="Timestamp desc",
                table_logical_name=AUTOMATION_LOG_TABLE_LOGICAL,
                use_display_names=True
            )
            logs = rows if rows else []
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch logs from Dataverse: {str(e)}"
            )
        
        if not logs:
            return JSONResponse(
                status_code=404,
                content={
                    "error": "No logs found for this RFP ID",
                    "rfp_id": request.rfp_id
                }
            )
        
        # Create enhanced report
        report = create_enhanced_error_report(
            rfp_id=request.rfp_id,
            logs=logs,
            context=request.context
        )
        
        return JSONResponse(
            status_code=200,
            content=report
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-rfp/formatted")
async def analyze_rfp_formatted_endpoint(request: AnalyzeRFPRequest):
    """
    Analyze RFP by ID and return formatted text report.
    Fetches logs from Dataverse automatically.
    """
    try:
        # Fetch logs from Dataverse
        logs = []
        try:
            rows = DATAVERSE.get_rows_from_dataverse(
                table_api_name=AUTOMATION_LOG_TABLE_API,
                filter_by={"RFP_ID": request.rfp_id},
                select_columns=["RunID", "Timestamp", "Category", "Action", "automation_status", "Message", "RFP_ID"],
                top=500,
                order_by="Timestamp desc",
                table_logical_name=AUTOMATION_LOG_TABLE_LOGICAL,
                use_display_names=True
            )
            logs = rows if rows else []
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch logs from Dataverse: {str(e)}"
            )
        
        if not logs:
            return PlainTextResponse(
                content=f"❌ No logs found for RFP ID: {request.rfp_id}",
                status_code=404
            )
        
        # Create enhanced report
        report = create_enhanced_error_report(
            rfp_id=request.rfp_id,
            logs=logs,
            context=request.context
        )
        
        formatted_text = format_error_report_for_display(report)
        
        return PlainTextResponse(
            content=formatted_text,
            status_code=200
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/quick-analysis")
async def quick_analysis_endpoint(logs: List[Dict[str, Any]] = Body(...)):
    """
    Quick analysis of logs without full report generation.
    Returns just the key findings.
    
    Example Request:
    ```json
    [
        {
            "Timestamp": "2025-11-26T15:06:49Z",
            "automation_status": "Success",
            "Action": "Submit",
            "Message": "Clicked button"
        },
        {
            "Timestamp": "2025-11-26T15:07:00Z",
            "automation_status": "Failed",
            "Action": "Submit",
            "Message": "Timeout"
        }
    ]
    ```
    """
    try:
        analysis = analyze_automation_logs(logs)
        
        # Return simplified response
        return JSONResponse(
            status_code=200,
            content={
                "status": analysis.get("status"),
                "error_summary": analysis.get("error_summary"),
                "last_successful_step": analysis.get("last_successful_step"),
                "failure_point": analysis.get("failure_point"),
                "total_errors": analysis.get("total_errors", 0),
                "total_warnings": analysis.get("total_warnings", 0),
                "suggestions": analysis.get("suggestions", [])
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check for error analysis service"""
    return {
        "status": "healthy",
        "service": "Enhanced Error Analysis API",
        "version": "1.0"
    }


# Example usage in main app.py:
# from routes.error_analysis_routes import router as error_analysis_router
# app.include_router(error_analysis_router)







