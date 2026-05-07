import asyncio
from dataclasses import dataclass


@dataclass
class SubprocessResult:
    return_code: int | None
    stdout: str
    stderr: str


async def run_subcommand(
    cmd: list[str],
    timeout_seconds: int | None = None,
) -> SubprocessResult | None:
    """Run subcommand and return result ONLY IF command finished within the timeout."""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if timeout_seconds:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout_seconds
            )
        else:
            stdout, stderr = await process.communicate()
    except TimeoutError:
        return None

    return SubprocessResult(
        stdout=stdout.decode(), stderr=stderr.decode(), return_code=process.returncode
    )
