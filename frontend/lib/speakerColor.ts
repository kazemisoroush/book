// A stable colour per speaker so a beat's border and cast swatch read at a glance. The narrator is
// the neutral quill-grey; every other character cycles through the casting-room accents.
const NARRATOR_ID = 1;
const NARRATOR_COLOR = "#9a9482";
const VOICE_COLORS = ["#6f9ec4", "#cc7fa2", "#c9a45c", "#6aa99b", "#cb8f6a", "#a98cc4"];

export function speakerColor(characterId: number | null | undefined): string {
  if (characterId == null || characterId === NARRATOR_ID) return NARRATOR_COLOR;
  return VOICE_COLORS[(characterId - 2 + VOICE_COLORS.length) % VOICE_COLORS.length];
}
