import pytest
from unittest.mock import patch, MagicMock
from app.core.security import (
    assess_command_risk,
    runner_available,
    validate_command_execution,
    validate_version_string,
)
from app.core.models import CommandSpec


class TestRunnerAvailable:
    """Test runner availability detection"""
    
    @patch('app.core.security.os.path.exists')
    @patch('app.core.security.subprocess.run')
    def test_runner_available_all_checks_pass(self, mock_run, mock_exists):
        """Test runner is available when all checks pass"""
        # Mock subprocess (ansible-playbook exists)
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock file existence
        mock_exists.return_value = True
        
        result = runner_available()
        assert result is True
    
    @patch('app.core.security.os.path.exists')
    @patch('app.core.security.subprocess.run')
    def test_runner_unavailable_no_ansible(self, mock_run, mock_exists):
        """Test runner unavailable when ansible-playbook missing"""
        # Mock subprocess (ansible-playbook does not exist)
        mock_run.return_value = MagicMock(returncode=1)
        
        # Mock file existence
        mock_exists.return_value = True
        
        result = runner_available()
        assert result is False
    
    @patch('app.core.security.os.path.exists')
    @patch('app.core.security.subprocess.run')
    def test_runner_unavailable_no_deploy_yml(self, mock_run, mock_exists):
        """Test runner unavailable when deploy.yml missing"""
        # Mock subprocess (ansible-playbook exists)
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock file existence (ansible/deploy.yml missing)
        def exists_side_effect(path):
            return "deploy.yml" not in path
        
        mock_exists.side_effect = exists_side_effect
        
        result = runner_available()
        assert result is False
    
    @patch('app.core.security.os.path.exists')
    @patch('app.core.security.subprocess.run')
    def test_runner_unavailable_no_inventory(self, mock_run, mock_exists):
        """Test runner unavailable when inventory.ini missing"""
        # Mock subprocess (ansible-playbook exists)
        mock_run.return_value = MagicMock(returncode=0)
        
        # Mock file existence (inventory.ini missing)
        def exists_side_effect(path):
            return "inventory.ini" not in path
        
        mock_exists.side_effect = exists_side_effect
        
        result = runner_available()
        assert result is False


class TestValidateVersionString:
    """Test version string validation"""
    
    def test_validate_v1(self):
        """Test simple version v1"""
        assert validate_version_string("v1") is True
    
    def test_validate_v10(self):
        """Test two-digit version v10"""
        assert validate_version_string("v10") is True
    
    def test_validate_v1_2_3(self):
        """Test semantic version"""
        assert validate_version_string("v1.2.3") is True
    
    def test_validate_v1_2_3_4(self):
        """Test version with many parts"""
        assert validate_version_string("v1.2.3.4") is True
    
    def test_validate_no_v_prefix(self):
        """Test invalid: no v prefix"""
        assert validate_version_string("1.2.3") is False
    
    def test_validate_capital_v(self):
        """Test invalid: capital V"""
        assert validate_version_string("V1.2.3") is False
    
    def test_validate_invalid_chars(self):
        """Test invalid: contains letters"""
        assert validate_version_string("v1.2.a") is False
    
    def test_validate_empty(self):
        """Test invalid: empty string"""
        assert validate_version_string("") is False
    
    def test_validate_just_v(self):
        """Test invalid: just 'v'"""
        assert validate_version_string("v") is False
    
    def test_validate_trailing_dot(self):
        """Test invalid: trailing dot"""
        assert validate_version_string("v1.2.") is False


class TestCommandRiskGuardrails:
    def test_stop_all_is_risky(self):
        spec = CommandSpec(command_type="stop", target_nodes=["node1", "node2", "node3"])
        risky, reason = assess_command_risk(spec)
        assert risky is True
        assert "downtime" in reason.lower()

    def test_scale_down_is_risky(self):
        spec = CommandSpec(command_type="scale", scale_direction="down", target_nodes=["node1"])
        risky, reason = assess_command_risk(spec)
        assert risky is True
        assert "scale down" in reason.lower()

    def test_validate_blocks_unconfirmed_risky_command(self):
        spec = CommandSpec(
            command_type="stop",
            target_nodes=["node1", "node2", "node3"],
            requires_confirmation=True,
            confirmed=False,
        )
        with pytest.raises(ValueError):
            validate_command_execution(spec)

    def test_validate_allows_confirmed_risky_command(self):
        spec = CommandSpec(
            command_type="stop",
            target_nodes=["node1", "node2", "node3"],
            requires_confirmation=True,
            confirmed=True,
        )
        validate_command_execution(spec)
