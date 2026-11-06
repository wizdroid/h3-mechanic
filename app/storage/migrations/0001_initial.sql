-- H3 Prompt Studio Initial Database Schema
-- Normative Reference: specification-0.3.md §6.1

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  notes TEXT DEFAULT '',
  default_settings TEXT,
  revision INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clips (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('T2VA','I2VA','FL2VA','L2VA','REF2VA')),
  name TEXT NOT NULL DEFAULT 'Clip',
  h3_model TEXT NOT NULL DEFAULT 'MiniMax-H3' CHECK(h3_model IN ('MiniMax-H3','MiniMax-H3-Max')),
  style_id TEXT NOT NULL DEFAULT 'plain' CHECK(style_id IN ('plain','80s-bollywood','cinematic-modern','modern-series','noir-thriller')),
  plain_style_pair TEXT NOT NULL DEFAULT 'Live-action, cinematic' CHECK(plain_style_pair IN (
    'Live-action, cinematic','2D-animated, cinematic','3D CG, cinematic','claymation, cinematic','watercolor, cinematic','vintage film, cinematic')),
  duration_s INTEGER NOT NULL,
  resolution TEXT NOT NULL,
  ratio TEXT NOT NULL,
  language TEXT NOT NULL DEFAULT 'English' CHECK(language IN ('English','Kannada','Hindi','Tamil','Telugu','Malayalam','Marathi','Bengali')),
  audio_policy TEXT NOT NULL DEFAULT 'dialogue_only' CHECK(audio_policy IN ('dialogue_only','custom','silence')),
  seed_text TEXT NOT NULL DEFAULT '',
  action_text TEXT NOT NULL DEFAULT '',
  custom_soundscape TEXT NOT NULL DEFAULT '',
  custom_music TEXT NOT NULL DEFAULT 'N/A',
  task_types_json TEXT NOT NULL DEFAULT '[]',
  task_types_touched INTEGER NOT NULL DEFAULT 0 CHECK(task_types_touched IN (0,1)),
  requested_shot_count INTEGER CHECK(requested_shot_count IS NULL OR requested_shot_count BETWEEN 1 AND 4),
  manual_draft INTEGER NOT NULL DEFAULT 0 CHECK(manual_draft IN (0,1)),
  manual_template TEXT NOT NULL DEFAULT '',
  wizard_step INTEGER NOT NULL DEFAULT 1 CHECK(wizard_step BETWEEN 1 AND 4),
  revision INTEGER NOT NULL DEFAULT 1,
  inputs_revision INTEGER NOT NULL DEFAULT 1,
  selected_prompt_id INTEGER,
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','generating','preflight','blocked','fixed','failed','exported')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK (
    (h3_model = 'MiniMax-H3' AND duration_s BETWEEN 4 AND 15 AND resolution IN ('768P','2K'))
    OR (h3_model = 'MiniMax-H3-Max' AND duration_s BETWEEN 5 AND 15 AND resolution IN ('480P','768P'))
  ),
  CHECK (
    (mode = 'T2VA' AND ratio IN ('21:9','16:9','4:3','1:1','3:4','9:16'))
    OR (mode IN ('I2VA','FL2VA','L2VA') AND ratio = 'adaptive')
    OR (mode = 'REF2VA' AND ratio IN ('adaptive','21:9','16:9','4:3','1:1','3:4','9:16'))
  )
);

CREATE TABLE IF NOT EXISTS references_tokens (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('image','video','audio')),
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  caption TEXT NOT NULL,
  role_hint TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL CHECK(position >= 1),
  source_file TEXT NOT NULL DEFAULT '',
  duration_ms INTEGER,
  width_px INTEGER,
  height_px INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, kind, ordinal),
  UNIQUE(clip_id, position),
  CHECK (kind = 'image' OR (width_px IS NULL AND height_px IS NULL)),
  CHECK (kind <> 'image' OR duration_ms IS NULL),
  CHECK (width_px IS NULL OR width_px > 0),
  CHECK (height_px IS NULL OR height_px > 0),
  CHECK (duration_ms IS NULL OR duration_ms BETWEEN 2000 AND 15000)
);

CREATE TABLE IF NOT EXISTS subjects (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  role TEXT NOT NULL CHECK(role IN ('person', 'character', 'crowd', 'body_part', 'face', 'hair', 'expression', 'pose', 'animal', 'creature', 'plant', 'robot', 'outfit', 'accessory', 'jewelry', 'footwear', 'headwear', 'makeup', 'tattoo', 'prop', 'weapon', 'vehicle', 'furniture', 'food', 'drink', 'tool', 'device', 'instrument', 'location', 'architecture', 'interior', 'landscape', 'background', 'weather', 'time_of_day', 'season', 'lighting', 'color_palette', 'texture', 'material', 'pattern', 'effect', 'particle', 'camera_angle', 'composition', 'style', 'art_medium', 'text', 'logo', 'symbol', 'other')),
  role_phrase TEXT NOT NULL DEFAULT '',
  pronoun TEXT NOT NULL DEFAULT 'her' CHECK(pronoun IN ('his','her','its')),
  outfit_noun TEXT NOT NULL DEFAULT 'outfit',
  appositive TEXT NOT NULL DEFAULT '',
  feature_list TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE IF NOT EXISTS shots (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
  end_ms INTEGER NOT NULL CHECK(end_ms > start_ms),
  size TEXT NOT NULL DEFAULT '',
  angle TEXT NOT NULL DEFAULT '',
  camera_move TEXT NOT NULL DEFAULT '',
  pacing TEXT NOT NULL DEFAULT 'action' CHECK(pacing IN ('silent','action')),
  events TEXT NOT NULL DEFAULT '',
  reference_anchors_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE IF NOT EXISTS subject_pictures (
  id INTEGER PRIMARY KEY,
  subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  reference_id INTEGER NOT NULL REFERENCES references_tokens(id) ON DELETE CASCADE,
  reference_role TEXT NOT NULL CHECK(reference_role IN (
    'identity_anchor','outfit','prop','location','composition_anchor',
    'framing_reference','first_frame','keyframe','last_frame')),
  anchor_shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  defines_text TEXT NOT NULL DEFAULT '',
  UNIQUE(subject_id, reference_id, reference_role)
);

CREATE TABLE IF NOT EXISTS speakers (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
  voice_source TEXT NOT NULL DEFAULT '',
  audio_reference_id INTEGER REFERENCES references_tokens(id) ON DELETE SET NULL,
  accent TEXT NOT NULL DEFAULT '',
  pronoun TEXT NOT NULL DEFAULT 'his' CHECK(pronoun IN ('his','her','its')),
  persona TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, display_name)
);

CREATE TABLE IF NOT EXISTS dialogue_lines (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  dest_shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  line_order INTEGER NOT NULL DEFAULT 1,
  speaker_id INTEGER NOT NULL REFERENCES speakers(id) ON DELETE CASCADE,
  speaker_id_2 INTEGER REFERENCES speakers(id) ON DELETE SET NULL,
  language TEXT NOT NULL CHECK(language IN ('English','Kannada','Hindi','Tamil','Telugu','Malayalam','Marathi','Bengali')),
  text_raw TEXT NOT NULL,
  text_in_prompt TEXT NOT NULL DEFAULT '',
  gloss TEXT NOT NULL DEFAULT '',
  delivery TEXT NOT NULL DEFAULT 'none' CHECK(delivery IN (
    'none','whisper','shout','command','mumble','sob','choked','plead','sarcastic','tender',
    'menacing','cold','deadpan','excited','breathless','nervous','laughing','furious',
    'interrogation','murmur','singing')),
  is_voiceover INTEGER NOT NULL DEFAULT 0 CHECK(is_voiceover IN (0,1)),
  crosses_cut INTEGER NOT NULL DEFAULT 0 CHECK(crosses_cut IN (0,1)),
  cutoff INTEGER NOT NULL DEFAULT 0 CHECK(cutoff IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  CHECK(speaker_id_2 IS NULL OR speaker_id_2 <> speaker_id)
);

CREATE TABLE IF NOT EXISTS onscreen_texts (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  shot_id INTEGER REFERENCES shots(id) ON DELETE SET NULL,
  text_raw TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal)
);

CREATE TABLE IF NOT EXISTS retention_markers (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
  area TEXT NOT NULL CHECK(area IN ('visual','audio')),
  subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  reference_id INTEGER REFERENCES references_tokens(id) ON DELETE CASCADE,
  parenthetical TEXT NOT NULL DEFAULT '',
  shot_ordinals_json TEXT NOT NULL DEFAULT '[]',
  marker TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  marker_source TEXT NOT NULL DEFAULT 'default' CHECK(marker_source IN ('user','default')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(clip_id, ordinal),
  CHECK((subject_id IS NULL) <> (reference_id IS NULL))
);

CREATE TABLE IF NOT EXISTS prompts (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  generation_id TEXT NOT NULL,
  stage TEXT NOT NULL CHECK(stage IN ('draft','fixed','variation')),
  inputs_revision INTEGER NOT NULL,
  summary_text TEXT NOT NULL DEFAULT '',
  body_template TEXT NOT NULL,
  body TEXT NOT NULL,
  char_count INTEGER NOT NULL CHECK(char_count >= 0),
  structured_payload_json TEXT,
  preflight_json TEXT,
  overrides_json TEXT NOT NULL DEFAULT '[]',
  fixer_retries INTEGER NOT NULL DEFAULT 0,
  drafter_model TEXT,
  ollama_seed INTEGER,
  stage_timings_json TEXT,
  prose_fallback INTEGER NOT NULL DEFAULT 0 CHECK(prose_fallback IN (0,1)),
  exported_filename TEXT,
  exported_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_references_clip ON references_tokens(clip_id, position);
CREATE INDEX IF NOT EXISTS idx_shots_clip ON shots(clip_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_lines_clip ON dialogue_lines(clip_id, line_order);
CREATE INDEX IF NOT EXISTS idx_prompts_clip ON prompts(clip_id, created_at);
CREATE INDEX IF NOT EXISTS idx_subject_pictures_subject ON subject_pictures(subject_id);
CREATE INDEX IF NOT EXISTS idx_speakers_clip ON speakers(clip_id);
CREATE INDEX IF NOT EXISTS idx_onscreen_clip ON onscreen_texts(clip_id);
CREATE INDEX IF NOT EXISTS idx_retention_clip ON retention_markers(clip_id);
