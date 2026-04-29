from pathlib import Path

from code_agent.agent import EngineeringCodeAgent, create_demo_project


def test_demo_scan(tmp_path: Path):
    demo = tmp_path / "demo_project"
    create_demo_project(str(demo))
    agent = EngineeringCodeAgent(str(demo))
    assert len(agent.index.files) > 0
    assert "requirements.txt" in agent.index.important_files


def test_log_analysis(tmp_path: Path):
    demo = tmp_path / "demo_project"
    create_demo_project(str(demo))
    agent = EngineeringCodeAgent(str(demo))
    result = agent.analyze_log("ModuleNotFoundError: No module named 'cv2'")
    assert result.error_type == "python_module_not_found"
