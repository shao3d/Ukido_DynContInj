# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.16.2] - 2025-01-13

### Added
- Repository reorganization for public presentation
- Professional project structure with clean root directory
- GitHub issue and PR templates

### Fixed
- Course launch dates corrected to 2026 (was incorrectly showing 2025)
- Archive branches moved to archive/* namespace

## [0.16.1] - 2025-01-10

### Fixed
- Critical formatting issue with paragraph breaks during translation
- Streaming translation now correctly preserves formatting
- Protected terms (Ukido, soft skills, Zoom) properly maintained

## [0.16.0] - 2025-01-09

### Added
- Full multilingual support (Russian, Ukrainian, English)
- Real-time translation with streaming
- Three new courses in development:
  - Critical Thinking (10-14 years)
  - Creative Laboratory (8-12 years)
  - Financial Literacy (9-14 years)

### Removed
- All VR mentions from knowledge base

## [0.15.0] - 2025-01-07

### Added
- SSE (Server-Sent Events) web chat interface
- Beautiful gradient UI with real-time streaming responses
- Docker support with multi-stage builds
- Railway deployment configuration
- Metadata display in chat (intent, user_signal, humor flag)

## [0.14.2] - 2025-01-10

### Fixed
- Optimized paragraph formatting in web interface
- Removed excessive empty lines between paragraphs

## [0.14.1] - 2025-01-09

### Fixed
- Time display bug (16:00 was showing as 16:)
- Added recognition for acknowledgment messages ("OK", "👍", emojis)
- Blocked humor generation for short messages

## [0.14.0] - 2025-01-07

### Added
- SSE web interface implementation
- Docker support for Railway deployment
- Health check endpoint with dynamic port support

## [0.13.5] - 2025-09-05

### Added
- HTTP timeout protection (30 seconds)
- API key validation at startup
- Full state persistence functionality
- Gemini caching for token optimization

### Fixed
- All critical production issues resolved

## [0.13.4] - 2024-09-05

### Changed
- Optimized Zhvanetsky humor for demonstrations
- Increased humor frequency from 10% to 57% for offtopic
- Increased character limit from 400 to 600
- Increased sentence limit from 3 to 5

### Fixed
- Critical humor validation issue

## [0.13.0-0.13.3] - 2024-09-03/04

### Added
- Production-ready prompt optimization (25% reduction)
- Code review and critical fixes plan

### Fixed
- Domain unification to ukido.com.ua
- CTA organic integration restored

## [0.12.x] - 2024-08-28/09-02

### Added
- PersistenceManager for dialogue preservation
- Office location and parking information
- Usage statistics rounding
- Variety in price_sensitive responses

### Fixed
- Mixed intent classification
- Document contradictions
- Transport understanding
- CTA HTML markers visibility

## Earlier Versions

See `docs/CLAUDE.md` for detailed version history prior to v0.12.