from tools.actions import ActionResult, ReceptionistActions

__all__ = ["ActionResult", "ReceptionistActions", "ToolServices", "build_livekit_tools"]


def __getattr__(name: str):
    if name in {"ToolServices", "build_livekit_tools"}:
        from tools.registry import ToolServices, build_livekit_tools

        return {"ToolServices": ToolServices, "build_livekit_tools": build_livekit_tools}[name]
    raise AttributeError(name)
