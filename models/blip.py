from dataclasses import dataclass

from models.blip_kind import BlipKind


@dataclass(frozen=True)
class Blip:
    kind: BlipKind
    val: any

    def __str__(self):
        if self.kind == BlipKind.WORD:
            return self.val
        elif self.kind == BlipKind.CLAP:
            return "👏"
        elif self.kind == BlipKind.SNAP:
            return "🫰"
