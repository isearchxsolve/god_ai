export interface AgentStatus {
  id: string;
  name: string;
  message: string;
  isStreaming: boolean;
  lastUpdate: number;
  agentType: 'scriptwriter' | 'art_director' | 'character_designer' | 'scene_designer' | 'storyboard_artist' | 'animator' | 'sound_director' | 'director';
  progress?: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface AgentDefinition {
  agentType: AgentStatus['agentType'];
  displayName: string;
  description: string;
  capabilities: string[];
}

export const AGENT_DEFINITIONS: AgentDefinition[] = [
  {
    agentType: 'scriptwriter',
    displayName: 'Scriptwriter',
    description: 'Generates narrative scripts from user ideas',
    capabilities: ['script_generation', 'dialogue_writing', 'story_structure'],
  },
  {
    agentType: 'art_director',
    displayName: 'Art Director',
    description: 'Sets visual tone, palette, and composition',
    capabilities: ['visual_direction', 'palette_selection', 'mood_boarding'],
  },
  {
    agentType: 'character_designer',
    displayName: 'Character Designer',
    description: 'Creates character reference sheets',
    capabilities: ['character_design', 'reference_sheets', 'consistency_locking'],
  },
  {
    agentType: 'scene_designer',
    displayName: 'Scene Designer',
    description: 'Designs environment and scene compositions',
    capabilities: ['environment_design', 'lighting', 'props'],
  },
  {
    agentType: 'storyboard_artist',
    displayName: 'Storyboard Artist',
    description: 'Creates frame-by-frame storyboards',
    capabilities: ['storyboard_frames', 'shot_composition', 'camera_movement'],
  },
  {
    agentType: 'animator',
    displayName: 'Animator',
    description: 'Animates frames into clips',
    capabilities: ['video_generation', 'motion_synthesis', 'frame_interpolation'],
  },
  {
    agentType: 'sound_director',
    displayName: 'Sound Director',
    description: 'Produces audio, music, and SFX',
    capabilities: ['music_generation', 'sfx_generation', 'voice_synthesis'],
  },
  {
    agentType: 'director',
    displayName: 'Director',
    description: 'Orchestrates all agents and final review',
    capabilities: ['orchestration', 'quality_review', 'final_approval'],
  },
];

export const getAgentDefinition = (agentType: AgentStatus['agentType']): AgentDefinition | undefined => {
  return AGENT_DEFINITIONS.find((a) => a.agentType === agentType);
};
