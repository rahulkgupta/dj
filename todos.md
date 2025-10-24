# DJ Audio Tagger - TODOs

## Completed ✅
- [x] Clean up and remove unused code
- [x] Remove old dspy_tagger versions
- [x] Remove duplicate/redundant processing scripts  
- [x] Update CLAUDE.md with current project structure
- [x] Remove Rekordbox integration
- [x] Implement 20-mood + 5-energy enforced tag system
- [x] Update tag_definitions.py with finalized mood/energy options
- [x] Update dspy_tagger.py with Pydantic enum validation
- [x] Test new system with existing audio features
- [x] Update CLAUDE.md with new tag system documentation

## In Progress 🔄

### Documentation
- [ ] Add examples of successful tag outputs to documentation
- [ ] Document the complete pipeline flow (local → Modal → download → apply tags)

## Pending Tasks 📝

### Self-Contained Script
- [ ] Figure out how to make the script self-contained
- [ ] Bundle all dependencies and modules
- [ ] Create single entry point for entire workflow
- [ ] Consider Docker or similar containerization

### Tag Standardization  
- [x] Standardize enums for tag values
- [x] Decide whether to constrain AI to predefined values or allow free generation
- [x] Create consistent tag schema across all versions
- [x] Implement validation for generated tags

### Bug Fixes
- [ ] Fix Modal deprecation warnings (keep_warm → min_containers, concurrency_limit → max_containers)

### LLM Prompt Enhancements
- [ ] Expand Librosa-derived context passed to DSPy (instrumentation heuristics, vocal detection, rhythmic feel, structural summary)
- [ ] Define tiered genre taxonomy (family + subgenre) and update prompt/normalization to reduce duplicate genre labels
