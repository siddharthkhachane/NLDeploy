from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional, Union


class DeploymentSpec(BaseModel):
    """Deployment specification schema"""
    target_version: str = Field(..., description="Target version to deploy (e.g., 'v2')")
    strategy: Literal["rolling"] = Field(default="rolling", description="Deployment strategy")
    batch_size: int = Field(default=1, description="Batch size (must be 1)")
    health_path: str = Field(default="/health", description="Health check endpoint path")
    retries: int = Field(default=30, description="Number of health check retries")
    delay_sec: float = Field(default=0.5, description="Delay between retries in seconds")
    
    @field_validator("batch_size")
    @classmethod
    def batch_size_must_be_one(cls, v):
        if v != 1:
            raise ValueError("batch_size must equal 1")
        return v
    
    @field_validator("target_version")
    @classmethod
    def target_version_required(cls, v):
        if not v:
            raise ValueError("target_version is required")
        return v


class CommandSpec(BaseModel):
    """Command execution specification (for non-deployment ops)"""
    command_type: Literal["stop", "restart", "scale"] = Field(..., description="Type of command")
    target_nodes: list[str] = Field(default_factory=lambda: ["node1", "node2", "node3"], description="Target nodes")
    
    @field_validator("target_nodes")
    @classmethod
    def target_nodes_valid(cls, v):
        if not v:
            raise ValueError("target_nodes cannot be empty")
        valid_nodes = {"node1", "node2", "node3"}
        for node in v:
            if node not in valid_nodes:
                raise ValueError(f"Invalid node: {node}. Must be one of {valid_nodes}")
        return v
