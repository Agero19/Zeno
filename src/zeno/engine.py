from __future__ import annotations

from dataclasses import dataclass

from .models import (
    MINUTES_PER_DAY,
    DayScheduleRequest,
    FixedBlock,
    FlexibleTask,
    ScheduledTask,
    TimelineResponse,
    TimelineSlot,
)


@dataclass(frozen=True)
class Interval:
    start: int
    end: int

    @property
    def duration(self) -> int:
        return self.end - self.start


class OptimizationEngine:
    """Greedy scheduler that prioritizes high-priority tasks into largest gaps."""

    def build_day_timeline(self, request: DayScheduleRequest) -> TimelineResponse:
        fixed_blocks = self._sorted_non_overlapping_fixed_blocks(request.fixed_blocks)
        available_gaps = self._available_gaps(
            fixed_blocks=fixed_blocks,
            transition_buffer_minutes=request.transition_buffer_minutes,
        )

        scheduled_tasks: list[ScheduledTask] = []
        unscheduled_tasks: list[FlexibleTask] = []

        prioritized_tasks = sorted(
            request.flexible_tasks,
            key=lambda task: (
                task.priority,
                -task.duration_minutes,
                task.title.lower(),
            ),
        )

        for task in prioritized_tasks:
            gap_index = self._largest_fitting_gap_index(
                available_gaps, task.duration_minutes
            )
            if gap_index is None:
                unscheduled_tasks.append(task)
                continue

            gap = available_gaps.pop(gap_index)
            start = gap.start
            end = start + task.duration_minutes

            scheduled_tasks.append(
                ScheduledTask(
                    id=task.id,
                    title=task.title,
                    category=task.category,
                    priority=task.priority,
                    start_minute=start,
                    end_minute=end,
                )
            )

            if end < gap.end:
                available_gaps.append(Interval(start=end, end=gap.end))

        timeline = self._compose_timeline(
            fixed_blocks=fixed_blocks, scheduled_tasks=scheduled_tasks
        )
        return TimelineResponse(
            transition_buffer_minutes=request.transition_buffer_minutes,
            timeline=timeline,
            scheduled_tasks=sorted(scheduled_tasks, key=lambda item: item.start_minute),
            unscheduled_tasks=unscheduled_tasks,
        )

    def _sorted_non_overlapping_fixed_blocks(
        self, blocks: list[FixedBlock]
    ) -> list[FixedBlock]:
        sorted_blocks = sorted(
            blocks, key=lambda block: (block.start_minute, block.end_minute)
        )
        for idx in range(1, len(sorted_blocks)):
            prev = sorted_blocks[idx - 1]
            curr = sorted_blocks[idx]
            if curr.start_minute < prev.end_minute:
                msg = f"Fixed blocks overlap: '{prev.id}' and '{curr.id}'"
                raise ValueError(msg)
        return sorted_blocks

    def _available_gaps(
        self, fixed_blocks: list[FixedBlock], transition_buffer_minutes: int
    ) -> list[Interval]:
        if not fixed_blocks:
            return [Interval(start=0, end=MINUTES_PER_DAY)]

        buffered: list[Interval] = []
        for block in fixed_blocks:
            buffered.append(
                Interval(
                    start=max(0, block.start_minute - transition_buffer_minutes),
                    end=min(
                        MINUTES_PER_DAY, block.end_minute + transition_buffer_minutes
                    ),
                )
            )

        merged = self._merge_intervals(buffered)
        gaps: list[Interval] = []
        cursor = 0
        for interval in merged:
            if cursor < interval.start:
                gaps.append(Interval(start=cursor, end=interval.start))
            cursor = max(cursor, interval.end)

        if cursor < MINUTES_PER_DAY:
            gaps.append(Interval(start=cursor, end=MINUTES_PER_DAY))
        return gaps

    def _merge_intervals(self, intervals: list[Interval]) -> list[Interval]:
        if not intervals:
            return []

        sorted_intervals = sorted(intervals, key=lambda item: (item.start, item.end))
        merged: list[Interval] = [sorted_intervals[0]]

        for current in sorted_intervals[1:]:
            last = merged[-1]
            if current.start <= last.end:
                merged[-1] = Interval(start=last.start, end=max(last.end, current.end))
            else:
                merged.append(current)
        return merged

    def _largest_fitting_gap_index(
        self, gaps: list[Interval], duration_minutes: int
    ) -> int | None:
        fitting = [
            (idx, gap.duration)
            for idx, gap in enumerate(gaps)
            if gap.duration >= duration_minutes
        ]
        if not fitting:
            return None
        return max(fitting, key=lambda item: item[1])[0]

    def _compose_timeline(
        self, fixed_blocks: list[FixedBlock], scheduled_tasks: list[ScheduledTask]
    ) -> list[TimelineSlot]:
        occupied: list[TimelineSlot] = []

        for block in fixed_blocks:
            occupied.append(
                TimelineSlot(
                    slot_type="fixed",
                    id=block.id,
                    title=block.title,
                    start_minute=block.start_minute,
                    end_minute=block.end_minute,
                )
            )

        for task in scheduled_tasks:
            occupied.append(
                TimelineSlot(
                    slot_type="task",
                    id=task.id,
                    title=task.title,
                    start_minute=task.start_minute,
                    end_minute=task.end_minute,
                    category=task.category,
                    priority=task.priority,
                )
            )

        occupied.sort(key=lambda item: (item.start_minute, item.end_minute))

        timeline: list[TimelineSlot] = []
        cursor = 0
        for slot in occupied:
            if cursor < slot.start_minute:
                timeline.append(
                    TimelineSlot(
                        slot_type="free",
                        id=f"free-{cursor}-{slot.start_minute}",
                        title="Free",
                        start_minute=cursor,
                        end_minute=slot.start_minute,
                    )
                )
            timeline.append(slot)
            cursor = max(cursor, slot.end_minute)

        if cursor < MINUTES_PER_DAY:
            timeline.append(
                TimelineSlot(
                    slot_type="free",
                    id=f"free-{cursor}-{MINUTES_PER_DAY}",
                    title="Free",
                    start_minute=cursor,
                    end_minute=MINUTES_PER_DAY,
                )
            )

        return timeline
