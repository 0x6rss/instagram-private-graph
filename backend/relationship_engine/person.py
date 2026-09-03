"""Person record + Evidence — pk basina tum kanitlari toplayan dataclass'lar."""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Evidence:
    """Tek bir sinyalin kaydi.

    source: 'phase29_like', 'phase30_tagger', 'phase32_real_connection', vb.
    weight: bu sinyal icin uygulanan WEIGHTS deger
    detail: serbest dict (media_id, ts, count, vb.)
    """
    source: str
    weight: float
    detail: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


@dataclass
class Person:
    pk: str
    username: str | None = None
    full_name: str | None = None
    is_private: bool | None = None
    is_verified: bool | None = None

                           
    follower_count: int | None = None
    following_count: int | None = None
    media_count: int | None = None
    mutual_followers_count: int | None = None
    chaining_score: float | None = None

                    
    profile_pic_id: str | None = None
    profile_pic_url: str | None = None
    avatar_uploader_pk: str | None = None
    avatar_uploaded_ts_ms: int | None = None

                                              
    cluster_module_count: int | None = None                            
    cluster_modules: list[str] = field(default_factory=list)

                             
    social_context: str | None = None
    context_class: str | None = None                                                                        
    profile_chaining_secondary_label: str | None = None
    phase32_rank: int | None = None                                                 
    phase32_seen_runs_count: int = 0                                                        
    phase32_all_ranks: list = field(default_factory=list)                      
    phase32_avg_rank: float | None = None
    phase32_min_rank: int | None = None
    phase32_max_rank: int | None = None

                                                                           
                                                                                 
    combined_presence_count: int = 0                                            
    combined_presence_ratio: float = 0.0                                               

                                                                          
                                                      
    probability_1hop: float = 0.0

                                                                           
                                                                              
    reciprocal_checked: bool = False
    reciprocal_target_in_their_chain: bool = False
    target_rank_in_their_chain: int | None = None
    their_chain_size: int | None = None
    inferred_relationship: str | None = None                                                    

                                                                           
                                                                          
                                  
    banyan_view_count: int = 0                                                       
    banyan_views: list = field(default_factory=list)                                                          
    banyan_best_rank: int | None = None                                      

                                                                          
                                                                          
                                           
    bootstrap_present: bool = False
    bootstrap_surfaces: list = field(default_factory=list)                     
    bootstrap_max_score: int | None = None                                         
    bootstrap_avg_rank: float | None = None                                          
    bootstrap_capture_count: int = 0                                              

                                                       
                                                                   
                                                                                 
                                                                        
                                                                              
                                                                    
    hop_class: str | None = None

                                               
    likes_to_x: list[dict] = field(default_factory=list)
    comments_to_x: list[dict] = field(default_factory=list)

                                               
    tags_of_target_count: int = 0                                                 
    tag_media_ids: list[str] = field(default_factory=list)
    co_tag_count: int = 0                                                                   
    co_tag_media_ids: list[str] = field(default_factory=list)
    mentioned_target: bool = False

                                 
    tag_search_hits: int = 0

                                                
                                                                          
                                                                    
    story_mentioned_by_target_count: int = 0
    story_mention_media_ids: list[str] = field(default_factory=list)
    story_mention_kinds: list[str] = field(default_factory=list)                                                           
    story_collab_with_target: bool = False
    target_story_locations: list[dict] = field(default_factory=list)                                              

                         
    news_events: list[dict] = field(default_factory=list)

                                                             
    friendship_status: dict = field(default_factory=dict)

                                                  
    shared_locations: list[dict] = field(default_factory=list)

                 
    cotag_2hop_neighbors: list[str] = field(default_factory=list)
    cotag_2hop_overlap: int = 0

                                   
    same_avatar_uploader: bool = False
    avatar_ts_close: bool = False
    avatar_ts_delta_seconds: int | None = None

                        
    evidence: list[Evidence] = field(default_factory=list)
    score: float = 0.0
    tier: str | None = None
    tier_rank: int | None = None

                                                           
    activity_timestamps: list[int] = field(default_factory=list)

                     
    last_seen_ts: int | None = None

    def add_evidence(self, source: str, weight: float, detail: dict | None = None):
        self.evidence.append(Evidence(source=source, weight=weight,
                                       detail=detail or {}))

    def merge_username(self, candidate: str | None):
        if candidate and not self.username:
            self.username = candidate

    def merge_full_name(self, candidate: str | None):
        if candidate and not self.full_name:
            self.full_name = candidate

    def merge_flag(self, attr: str, value: Any):
        cur = getattr(self, attr, None)
        if cur is None and value is not None:
            setattr(self, attr, value)

    def to_dict(self) -> dict:
        d = asdict(self)
                                                                             
        return d


class PersonRegistry:
    """pk -> Person, ekleme idempotent."""

    def __init__(self):
        self._by_pk: dict[str, Person] = {}

    def get_or_create(self, pk, username: str | None = None) -> Person:
        pk_s = str(pk)
        if pk_s not in self._by_pk:
            self._by_pk[pk_s] = Person(pk=pk_s, username=username)
        else:
            self._by_pk[pk_s].merge_username(username)
        return self._by_pk[pk_s]

    def __contains__(self, pk):
        return str(pk) in self._by_pk

    def __iter__(self):
        return iter(self._by_pk.values())

    def __len__(self):
        return len(self._by_pk)

    def all(self) -> list[Person]:
        return list(self._by_pk.values())

    def by_pk(self, pk) -> Person | None:
        return self._by_pk.get(str(pk))

    def drop(self, pk):
        self._by_pk.pop(str(pk), None)
