# Created by: Randy Grizzelli
# Email: grizzellir@gmail.com
# GitHub: https://github.com/rsgrizz
# Version: v.5
# Date: 5/19/2026
# Purpose: BFS-based multi-step conversion path planning and command generation.

import logging
import os
from typing import Optional, List
from app.core.models import (
    FileFormat,
    PathRisk,
    PlanConfidence,
    ConversionStep,
    ConversionPlan,
    PlannerError
)
from app.core.conversion_registry import ConversionRegistry

logger = logging.getLogger(__name__)

class ConversionPlanner:
    """Computes single-step or multi-step execution plans between source and target file formats
    using a deterministic shortest-path solver over registered edges.
    """

    @classmethod
    def plan_conversion(
        cls,
        source: FileFormat,
        target: FileFormat,
        input_path: str = "",
        output_path: str = ""
    ) -> ConversionPlan:
        """Generates a ConversionPlan to convert the source format into the target format.
        Raises PlannerError if no conversion path is available or if input/output constraints fail.
        """
        logger.info(f"Planning conversion path from {source.value} to {target.value}")

        input_path = cls._normalize_external_path(input_path)
        output_path = cls._normalize_external_path(output_path)
        
        if source == FileFormat.UNKNOWN or target == FileFormat.UNKNOWN:
            raise PlannerError(f"Cannot convert from/to UNKNOWN format. Source: {source.value}, Target: {target.value}")

        if source == target:
            raise PlannerError(f"Source and target formats are identical ({source.value}). No conversion required.")

        edges = ConversionRegistry.get_supported_edges()
        
        # Simple Dijkstra's Shortest Path Solver to find the lowest cost path
        adj = {fmt: [] for fmt in FileFormat}
        for edge in edges:
            adj[edge.source].append((edge.target, edge.weight, edge))

        # Priority queue holds (cumulative_weight, sequence_id, current_node, path_taken_edges)
        import heapq
        pq = [(0.0, 0, source, [])]
        min_weight = {fmt: float('inf') for fmt in FileFormat}
        min_weight[source] = 0.0
        
        sequence_id = 0
        best_path = None

        while pq:
            weight, _, current, path = heapq.heappop(pq)

            if current == target:
                best_path = path
                break

            if weight > min_weight[current]:
                continue

            for neighbor, edge_weight, edge in adj[current]:
                next_weight = weight + edge_weight
                # Tie-breaker: prefer intermediate RAW format if cumulative weights are equivalent
                if neighbor == FileFormat.RAW:
                    next_weight -= 0.001  # small discount to prefer RAW canonical intermediate
                
                if next_weight < min_weight[neighbor]:
                    min_weight[neighbor] = next_weight
                    sequence_id += 1
                    heapq.heappush(pq, (next_weight, sequence_id, neighbor, path + [edge]))

        if not best_path:
            logger.error(f"No valid conversion path found from {source.value} to {target.value}")
            raise PlannerError(f"Unsupported conversion path: {source.value} ➔ {target.value}")

        # Assemble conversion steps from the computed path
        steps: List[ConversionStep] = []
        for i, edge in enumerate(best_path):
            step_num = i + 1
            is_intermediate = (i < len(best_path) - 1)

            # Assign file paths for this step
            if i == 0:
                step_input = input_path if input_path else "source_image"
            else:
                step_input = steps[-1].output_file

            if not is_intermediate:
                step_output = output_path if output_path else "target_image"
            else:
                if output_path:
                    # Construct intermediate file in the same directory as the target output
                    base, _ = os.path.splitext(output_path)
                    step_output = f"{base}_temp_step{step_num}.raw"
                else:
                    step_output = f"intermediate_temp_step{step_num}.raw"

            # Parse template command tokens securely
            output_no_ext, _ = os.path.splitext(step_output)
            command_args = []
            for token in edge.command_template_tokens:
                formatted_token = token.format(
                    input=step_input,
                    output=step_output,
                    output_no_ext=output_no_ext
                )
                command_args.append(formatted_token)

            step = ConversionStep(
                step_num=step_num,
                source_format=edge.source,
                target_format=edge.target,
                command_args=command_args,
                input_file=step_input,
                output_file=step_output,
                backend_tool=edge.backend_tool,
                command_template_tokens=edge.command_template_tokens,
                notes=edge.notes,
                is_intermediate=is_intermediate,
                experimental=edge.experimental,
                risk=PathRisk.EXPERIMENTAL if edge.experimental else PathRisk.STABLE
            )
            steps.append(step)

        # Estimate temp file bytes based on steps
        estimated_temp_bytes = 0
        if len(steps) > 1 and input_path and os.path.exists(input_path):
            # Estimate intermediate temp file size to be equal to the source file size
            try:
                estimated_temp_bytes = os.path.getsize(input_path) * (len(steps) - 1)
            except Exception:
                pass

        plan = ConversionPlan(steps=steps, estimated_temp_bytes=estimated_temp_bytes)
        logger.info(f"Plan constructed successfully: {len(steps)} step(s). Experimental: {plan.has_experimental}")
        return plan

    @staticmethod
    def _normalize_external_path(path: str) -> str:
        """Normalize Windows paths before passing them to external CLI tools.

        Qt file dialogs return paths with forward slashes on Windows. Most tools
        tolerate that, but libewf/ewfexport treats paths like ``C:/...`` as
        invalid after applying its extended-path prefix. Keep non-Windows and
        POSIX-style test paths unchanged.
        """
        if not path or os.name != "nt":
            return path

        stripped = path.strip('"')
        is_drive_path = len(stripped) >= 3 and stripped[1] == ":" and stripped[2] in ("/", "\\")
        is_unc_path = stripped.startswith(("//", "\\\\"))

        if is_drive_path or is_unc_path:
            return os.path.normpath(stripped)

        return path
