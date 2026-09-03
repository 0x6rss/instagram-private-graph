"""Skor agirliklari, tier esikleri ve dosya isimleri tek noktada."""

import os

                                              
APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
DEFAULT_ARTIFACT_ROOT = os.path.join(APP_ROOT, 'data', 'artifacts')

                                                                       
OUTPUT_SUBDIR = 'relationships'

                                                                             
                                                                             
                                                                           
                                                
APILER_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'apiler')

                                                                      
                                                                     
      
TARGET_FOLLOWER_COVERAGE_PCT = 0.60


                                                                      
                                                     
WEIGHTS = {
                                                         
    'stable_inner_15_15':       50,                          
    'strong_signal_75pct':      25,                          
    'weak_sampled':              5,                   

                                                 
                                                                               
                                                                                
                                                                                  
                                   
    'p32_real_top':             30,                                                 
    'p32_real_mid':             12,                                   
    'p32_real_tail':             0,                                                        
    'p32_other_context':         8,                                     
    'p32_no_context':            5,
    'p32_only_suggested':      -25,                                           

                                                                              
                                                                           
                                                          
    'verification_1hop_stable':       0,                                           
    'verification_1hop_strong':      15,                                      
    'verification_1hop_confirmed':   12,                               
    'verification_1hop_likely':       0,                                          
    'verification_2hop_suspect':    -20,                                   

                                                                 
    'p26_chain_present':        10,
    'p26_chaining_score_high':  10,                                     

                                            
    'p29_like_per':              5,             
    'p29_comment_per':          12,                               

                                        
    'p30_tagger_per':           20,                                       
    'p30_co_tagged_per':         8,                                            
    'p30_mention_per':          10,                                     

                                                  
    'bidirectional_bonus':      40,

                                                 
    'p31_event_per':             6,

                                        
    'p26_tag_search_per':       15,

                                                             
    'fs_following_target':      15,                          
    'fs_followed_by_target':    20,                                                       
    'fs_outgoing_request':       8,
    'fs_incoming_request':      10,
    'fs_mutual_follow':          5,             
    'fs_blocking':              -50,
    'fs_restricted':            -10,
                                                             
    'fs_is_bestie':             40,                                          
    'fs_subscribed':            30,                                         
    'fs_is_feed_favorite':      25,                             
    'fs_muting':               -10,                               

                                                            
    'mutual_followers_count_factor': 0.5,                                   
    'mutual_followers_max_bonus': 25,

                        
    'cotag_2hop_neighbor':       6,

                                                      
    'same_location_per':        12,

                                               
    'avatar_uploader_match':    30,                     
    'avatar_close_timestamp':    8,                                          

                            
    'recent_activity_bonus':     5,                           

                                                                           
    'is_verified_penalty':      -8,

                                                                                
                                                                                  
                                                                             
                                                                          
                                                                         
    'story_mention_per':         15,                      
    'story_mention_repeat_bonus': 5,                                                       
    'story_collab_per':          25,                                         
    'story_q_response_per':      18,                                                  
    'story_shared_location_per': 10,                                                          

                                                                          
                                                                                 
                                                                              
                                                                      
                                        
    'bootstrap_besties_present':       50,                                        
    'bootstrap_dm_recipient':          30,                                  
    'bootstrap_autocomplete_top':      25,                                                      
    'bootstrap_autocomplete_mid':      15,                             
    'bootstrap_autocomplete_tail':      8,                                      
    'bootstrap_section_test':          10,                           
    'bootstrap_multi_capture_bonus':   15,                                       
}


                                                                     
                                                                          
TIER_THRESHOLDS = [
    ('verified',           99),                             
    ('high_probability',   80),                     
    ('medium_probability', 40),                                      
    ('low_probability',    15),                                     
    ('noise',               0),                                   
]


                               
RECENT_DAYS = 30
AVATAR_TS_WINDOW_SECONDS = 60                                                
COTAG_2HOP_MIN_OVERLAP = 2                                                     

                                                                
 
                                                                              
                                                                        
                                                                         
                                                                                
                                   
P32_RANK_TOP_PCT  = 0.40                                              
P32_RANK_MID_PCT  = 0.75                                             
                                                                            

                                                                            
                                                                                
            
A_STRONG_MIN_PCT      = 0.33                                           
A_MID_MIN_PCT         = 0.13                                         
A_TWO_HOP_MAX_PCT     = 0.07                                          

                                                                
                                                                                
                                                                        
                                                                         
 
                                                    
                                                
                                                                    
                                      
                                                                      
                                                                 
PRESENCE_RATIO_STABLE     = 0.55
PRESENCE_RATIO_STRONG     = 0.30
PRESENCE_RATIO_CONFIRMED  = 0.15
PRESENCE_RATIO_LIKELY     = 0.06

PRESENCE_COUNT_STABLE     = 10                                                  
PRESENCE_COUNT_STRONG     = 6
PRESENCE_COUNT_CONFIRMED  = 3
PRESENCE_COUNT_LIKELY     = 2

                                                                                  
                                                                 

                                                               
ARTIFACT_FILES = {
    'cluster_union':        'cluster_union.json',
    'discover_p32':         'discover_chaining_phase32.json',
    'archeology_p29':       'archeology_phase29.json',
    'tagged_feed':          'tagged_feed.json',
    'tag_search_cluster':   'tag_search_cluster.json',
    'news_inbox':           'news_inbox_phase31.json',
    'chaining_cluster':     'chaining_cluster.json',
    'presence_intel':       'presence_intel.json',
    'phase34_followgraph':  'phase34_followgraph.json',
    'target_internal':      'target_internal_phase33.json',
    'critical_intel':       'critical_intel.json',
    'reciprocal_phase35':   'reciprocal_phase35.json',
    'banyan_phase37':       'banyan_phase37.json',
                                                                          
                                                                          
                                                                                   
                                                                             
                                                     
    'story_phase38':        'story_phase38.json',
}
