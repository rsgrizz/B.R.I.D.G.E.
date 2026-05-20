# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.6
# Date: 5/20/2026
# Purpose: Operations validation, disk space checks, and dry-run report generation.

import logging
import shutil
from pathlib import Path
from app.core.models import ConversionPlan

logger = logging.getLogger(__name__)

class ConversionService:
    """Provides platform checks and validation safeguards before running conversion tasks."""

    @staticmethod
    def check_disk_space(target_path: str, required_bytes: int) -> bool:
        """Verifies if the target drive partition has enough free space plus a 5% margin."""
        logger.info(f"Checking disk space at {target_path} for required: {required_bytes} bytes")
        
        path = Path(target_path).parent
        if not path.exists():
            # If path does not exist, check its parent recursively
            path = path.resolve()
            while not path.exists():
                path = path.parent
                
        try:
            total, used, free = shutil.disk_usage(path)
            # Add a 5% safety overhead margin
            effective_required = int(required_bytes * 1.05)
            logger.info(f"Available free space: {free} bytes. Effective required: {effective_required} bytes.")
            return free >= effective_required
        except Exception as e:
            logger.error(f"Failed to check disk usage: {e}")
            return False

    @staticmethod
    def verify_write_access(directory_path: str) -> bool:
        """Verifies write permissions inside the destination directory by writing a tiny temp file."""
        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            return False
        try:
            temp_file = path / ".forensic_write_test"
            with open(temp_file, "w") as f:
                f.write("test")
            temp_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Write validation failed on folder: {directory_path} with error: {e}")
            return False

    @staticmethod
    def generate_dry_run_report(plan: ConversionPlan) -> str:
        """Generates a detailed, human-readable text report summarizing the execution steps of a conversion plan."""
        report = []
        report.append("==================================================")
        report.append("          CONVERSION PLAN DRY RUN REPORT          ")
        report.append("==================================================")
        report.append(f"Total steps: {plan.total_steps}")
        report.append(f"Features experimental path: {plan.has_experimental}")
        report.append("")
        
        for step in plan.steps:
            report.append(f"Step {step.step_num}: {step.source_format.value} ➔ {step.target_format.value}")
            report.append(f"  Tool to execute: {step.command_args[0]}")
            report.append(f"  Command line: {' '.join(step.command_args)}")
            report.append(f"  Input:  {step.input_file}")
            report.append(f"  Output: {step.output_file}")
            report.append(f"  Is Intermediate: {step.is_intermediate}")
            report.append(f"  Risk Profile:    {step.risk.value}")
            report.append("")
            
        report.append("==================================================")
        return "\n".join(report)
