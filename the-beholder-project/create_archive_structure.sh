#!/usr/bin/env bash
# Create LIFE_ARCHIVE directory structure per spec Section 4

ROOT="LIFE_ARCHIVE"

# Create all directories
mkdir -p "$ROOT"/{00_RAW/{google/{gmail,drive,photos,youtube,calendar,contacts,takeout/incoming},whatsapp/incoming,linkedin/incoming,github,git/repos,lms,social,documents,images,audio,video,other},01_MANIFEST,02_PROCESSED/{ocr,transcripts,extracted_metadata,thumbnails},03_NORMALIZED/{documents,emails,conversations,events,projects,people,organizations,creative_works,git_commits},04_TIMELINE,05_ENTITIES/{people,organizations,places,projects,technologies,concepts},06_KNOWLEDGE_GRAPH/{nodes,edges,graph_exports},07_INDEX/{lexical,semantic,metadata},08_RESEARCH/{questions,investigations,hypotheses,findings,contradictions,discoveries},09_EVIDENCE/{evidence_chains,citations,screenshots,source_maps},10_CREATIVE/{films,writing,philosophy,photography,audio,software,intellectual_frameworks,unfinished,monetizable},11_PUBLICATION/{linkedin,articles,books,essays,talks,website,documentary,social},12_AUDIT/{pipeline_runs,quality,validation,errors},99_PRIVATE/{secrets,credentials,restricted}}

# Create .gitkeep files for empty directories
find "$ROOT" -type d -empty -exec touch {}/.gitkeep \;

echo "✓ Archive structure created at $ROOT/"
ls -1 "$ROOT/"
