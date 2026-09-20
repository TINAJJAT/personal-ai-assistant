"""Validated calculator tool."""

import math
import operator
from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field, FiniteFloat


OPERATIONS = {
    "add": operator.add,
    "subtract": operator.sub,
    "multiply": operator.mul,
    "divide": operator.truediv,
}


class CalculatorInput(BaseModel):
    a: FiniteFloat = Field(description="First number.")
    b: FiniteFloat = Field(description="Second number.")
    operation: Literal["add", "subtract", "multiply", "divide"] = Field(
        description="Operation to apply to a and b, in that order."
    )


@tool(args_schema=CalculatorInput)
def calculator_tool(
    a: float,
    b: float,
    operation: str,
) -> float:
    """Calculate a + b, a - b, a * b, or a / b."""
    if operation == "divide" and b == 0:
        raise ValueError("Cannot divide by zero.")

    result = OPERATIONS[operation](a, b)

    if not math.isfinite(result):
        raise ValueError("The result exceeds the supported numeric range.")

    return result