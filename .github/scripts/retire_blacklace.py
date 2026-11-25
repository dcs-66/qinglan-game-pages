from pathlib import Path
import sys

site = Path(sys.argv[1] if len(sys.argv) > 1 else "site")

models_js = site / "js/data/character-models.js"
text = models_js.read_text(encoding="utf-8")
start_marker = "  ,blacklace: {"
end_marker = "  // ---- 示例"
if start_marker in text:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    text = text[:start] + text[end:]
    models_js.write_text(text, encoding="utf-8")
if "blacklace" in models_js.read_text(encoding="utf-8"):
    raise SystemExit("character-models.js still references blacklace")

character_js = site / "js/player/character.js"
js = character_js.read_text(encoding="utf-8")
old = "function switchCharacter(id, onDone) {\n  if (!CHARACTER_MODELS[id]) return;"
new = """function switchCharacter(id, onDone) {
  if (!CHARACTER_MODELS[id]) {
    // 旧存档可能记着已经下线的形貌 id；回落到当前仍显示的形貌，
    // 避免读档后 player.currentCharacter 继续指向一张不存在的卡片。
    if (typeof player !== 'undefined' && player) {
      player.currentCharacter = (typeof currentCharacterId !== 'undefined' && currentCharacterId) ? currentCharacterId : 'mech';
    }
    if (typeof saveGameSilent === 'function') saveGameSilent();
    if (onDone) onDone(null, true);
    return;
  }"""
if old in js:
    js = js.replace(old, new, 1)
    character_js.write_text(js, encoding="utf-8")
elif "if (!CHARACTER_MODELS[id]) {" not in js:
    raise SystemExit("character.js fallback patch target not found")

model = site / "assets/models/blacklace_lady.glb"
if model.exists():
    model.unlink()

print("retired blacklace:", models_js)
print("model exists:", model.exists())
