import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import WorkflowRunStatus, WorkflowStepStatus
from app.services.workflow_service import WorkflowService


class WorkflowServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        self.service = WorkflowService()

    def test_start_run_defaults_to_running_with_empty_input(self):
        with self.SessionLocal() as db:
            run = self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")

        self.assertEqual(run.status, WorkflowRunStatus.RUNNING)
        self.assertEqual(run.input_json, {})
        self.assertIsNone(run.session_id)
        self.assertIsNone(run.cycle_index)
        self.assertIsNotNone(run.id)

    def test_finish_run_sets_status_output_and_finished_at(self):
        with self.SessionLocal() as db:
            run = self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")
            self.assertIsNone(run.finished_at)

            finished = self.service.finish_run(
                db,
                run,
                status=WorkflowRunStatus.SUCCEEDED,
                decision_id=7,
                output_json={"summary_label": "done"},
            )

        self.assertEqual(finished.status, WorkflowRunStatus.SUCCEEDED)
        self.assertEqual(finished.decision_id, 7)
        self.assertEqual(finished.output_json, {"summary_label": "done"})
        self.assertIsNotNone(finished.finished_at)

    def test_record_step_attaches_to_run(self):
        with self.SessionLocal() as db:
            run = self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")

            step = self.service.record_step(
                db,
                run,
                step_name="market_agent",
                status=WorkflowStepStatus.SUCCEEDED,
                output_json={"candidate_count": 2},
            )

            reloaded = self.service.get_run(db, run.id)

        self.assertEqual(step.run_id, run.id)
        self.assertEqual(step.step_name, "market_agent")
        self.assertEqual(len(reloaded.steps), 1)
        self.assertEqual(reloaded.steps[0].output_json, {"candidate_count": 2})

    def test_list_runs_orders_newest_first_and_clamps_limit(self):
        with self.SessionLocal() as db:
            for _ in range(3):
                self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")

            runs = self.service.list_runs(db, limit=0)
            all_runs = self.service.list_runs(db, limit=999)

        # limit=0 clamps up to 1; 999 clamps down to 200 (still returns all 3 here)
        self.assertEqual(len(runs), 1)
        self.assertEqual(len(all_runs), 3)
        self.assertGreaterEqual(all_runs[0].id, all_runs[1].id)
        self.assertGreaterEqual(all_runs[1].id, all_runs[2].id)

    def test_list_runs_for_session_orders_by_cycle_index(self):
        with self.SessionLocal() as db:
            self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=1, cycle_index=2
            )
            self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=1, cycle_index=0
            )
            self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=1, cycle_index=1
            )
            # Different session -- must not show up in session 1's results.
            self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=2, cycle_index=0
            )

            runs = self.service.list_runs_for_session(db, session_id=1)

        self.assertEqual([run.cycle_index for run in runs], [0, 1, 2])
        self.assertTrue(all(run.session_id == 1 for run in runs))

    def test_fail_running_runs_for_session_only_touches_running_rows_in_that_session(self):
        with self.SessionLocal() as db:
            running_in_session = self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=1, cycle_index=0
            )
            already_finished = self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=1, cycle_index=1
            )
            self.service.finish_run(db, already_finished, status=WorkflowRunStatus.SUCCEEDED)
            running_in_other_session = self.service.start_run(
                db, workflow_name="agent.run_once", trigger_source="worker", session_id=2, cycle_index=0
            )

            self.service.fail_running_runs_for_session(db, session_id=1, error_message="session crashed")

            reloaded_running = self.service.get_run(db, running_in_session.id)
            reloaded_finished = self.service.get_run(db, already_finished.id)
            reloaded_other = self.service.get_run(db, running_in_other_session.id)

        self.assertEqual(reloaded_running.status, WorkflowRunStatus.FAILED)
        self.assertEqual(reloaded_running.error_message, "session crashed")
        self.assertIsNotNone(reloaded_running.finished_at)
        # Already-finished run in the same session is untouched.
        self.assertEqual(reloaded_finished.status, WorkflowRunStatus.SUCCEEDED)
        self.assertIsNone(reloaded_finished.error_message)
        # A RUNNING row in a *different* session is untouched.
        self.assertEqual(reloaded_other.status, WorkflowRunStatus.RUNNING)

    def test_get_latest_run_for_decision_returns_most_recent(self):
        with self.SessionLocal() as db:
            older = self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")
            self.service.finish_run(db, older, status=WorkflowRunStatus.SUCCEEDED, decision_id=5)
            newer = self.service.start_run(db, workflow_name="agent.run_once", trigger_source="manual")
            self.service.finish_run(db, newer, status=WorkflowRunStatus.SUCCEEDED, decision_id=5)

            latest = self.service.get_latest_run_for_decision(db, decision_id=5)

        self.assertEqual(latest.id, newer.id)


if __name__ == "__main__":
    unittest.main()
