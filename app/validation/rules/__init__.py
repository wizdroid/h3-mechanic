"""Registers all H3 preflight validation rules into the canonical registry."""

from app.validation.registry import default_registry

from app.validation.rules.all_modes import (
    PF01_TemplateIntegrity,
    PF02_ShotTimestamps,
    PF03_ShotBudgets,
    PF04_CameraPhrases,
    PF05_FaceHeuristic,
    PF06_SpeechExpansion,
    PF07_DialoguePunctuation,
    PF08_SoundFields,
    PF08b_MoodWords,
    PF09_CharacterLimitAndFences,
    PF10_EnglishProseCheck,
    PF11_RatioConcrete,
    PF12_ShotPartition,
    PF13_VideoModelMatrix,
)

from app.validation.rules.ref2va_and_cross import (
    PF20_ReferenceLimits,
    PF21_SummaryTaskTypes,
    PF22_RetentionMarkers,
    PF23_SubjectDefinitionsFormulas,
    PF24_StyleSentenceBeforeShot1,
    PF25_SpeakingSubjectsNotation,
    PF26_DetailedDescriptionWordCount,
    PF27_TokenContamination,
    PF28_TemplateIntegrity,
    PF29_PlanProseAgreement,
    PF30_StalePrompt,
    PF31_NativeScriptInput,
    PF32_OnScreenTextLength,
    PF33_FillerAndTagStack,
    PF34_SoundLexicon,
    PF35_HouseAudioSentence,
)

ALL_RULES = [
    PF01_TemplateIntegrity,
    PF02_ShotTimestamps,
    PF03_ShotBudgets,
    PF04_CameraPhrases,
    PF05_FaceHeuristic,
    PF06_SpeechExpansion,
    PF07_DialoguePunctuation,
    PF08_SoundFields,
    PF08b_MoodWords,
    PF09_CharacterLimitAndFences,
    PF10_EnglishProseCheck,
    PF11_RatioConcrete,
    PF12_ShotPartition,
    PF13_VideoModelMatrix,
    PF20_ReferenceLimits,
    PF21_SummaryTaskTypes,
    PF22_RetentionMarkers,
    PF23_SubjectDefinitionsFormulas,
    PF24_StyleSentenceBeforeShot1,
    PF25_SpeakingSubjectsNotation,
    PF26_DetailedDescriptionWordCount,
    PF27_TokenContamination,
    PF28_TemplateIntegrity,
    PF29_PlanProseAgreement,
    PF30_StalePrompt,
    PF31_NativeScriptInput,
    PF32_OnScreenTextLength,
    PF33_FillerAndTagStack,
    PF34_SoundLexicon,
    PF35_HouseAudioSentence,
]

for rule_cls in ALL_RULES:
    default_registry.register(rule_cls)
