from typing import List, Optional, Any
from llama_index.core.bridge.pydantic import BaseModel
from llama_index.core.query_engine import (
    BaseQueryEngine
)
from llama_index.core import PromptTemplate
from llama_index.llms.gemini import Gemini
from llama_index.core.llms import LLM
from llama_index.core.response_synthesizers import TreeSummarize
from llama_index.core.workflow import (
    Workflow,
    Event,
    StartEvent,
    StopEvent,
    step,
)
import os, json

class Answer(BaseModel):
    """Answer model."""

    choice: int
    reason: str

class Answers(BaseModel):
    """List of answers model."""

    answers: List[Answer]

class ChooseQueryEngineEvent(Event):
    """Query engine event."""

    answers: Answers
    query_str: str

class SynthesizeAnswersEvent(Event):
    """Synthesize answers event."""

    responses: List[Any]
    query_str: str

class RouterQueryWorkflow(Workflow):
    """Router query workflow."""

    def __init__(
        self,
        query_engines: List[BaseQueryEngine],
        choice_descriptions: Optional[List[str]] = None,
        router_prompt: Optional[PromptTemplate] = None,
        timeout: Optional[float] = 10.0,
        disable_validation: bool = False,
        verbose: bool = False,
        llm: Optional[LLM] = None,
        summarizer: Optional[TreeSummarize] = None,
    ):
        """Constructor"""

        super().__init__(timeout=timeout, disable_validation=disable_validation, verbose=verbose)

        # Load configs first
        self.config = self._load_configs()
        self.prompts = self.config["prompts"]

        # Create default prompts and descriptions
        self.doc_metadata_extra_str = self.prompts["doc_metadata_extra"]["text"]
        self._default_router_prompt = PromptTemplate(self.prompts["router_prompt"]["template"])
        self._default_tool_doc_desc = self.prompts["tool_descriptions"]["doc_query_engine"].format(
            doc_metadata_extra=self.doc_metadata_extra_str
        )
        self._default_tool_chunk_desc = self.prompts["tool_descriptions"]["chunk_query_engine"].format(
            doc_metadata_extra=self.doc_metadata_extra_str
        )
        
        # Store query engines
        self.query_engines = query_engines
        
        # Use provided values or defaults
        self.router_prompt = router_prompt or self._default_router_prompt
        self.choice_descriptions = choice_descriptions or [self._default_tool_doc_desc, self._default_tool_chunk_desc]
        self.llm = llm or Gemini(temperature=0, model="gemini-2.0-flash-001")
        self.summarizer = summarizer or TreeSummarize()


    def _load_configs(self):
        """Load prompts from JSON config file."""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            return json.load(f)

    def _get_choice_str(self, choices):
        """String of choices to feed into LLM."""

        choices_str = "\n\n".join([f"{idx+1}. {c}" for idx, c in enumerate(choices)])
        return choices_str

    async def _query(self, query_str: str, choice_idx: int):
        """Query using query engine"""

        query_engine = self.query_engines[choice_idx]
        response = await query_engine.aquery(query_str)
        return response


    @step()
    async def choose_query_engine(self, ev: StartEvent) -> ChooseQueryEngineEvent:
        """Choose query engine."""

        # get query str
        query_str = ev.get("query_str")
        if query_str is None:
            raise ValueError("'query_str' is required.")

        # partially format prompt with number of choices and max outputs
        router_prompt1 = self.router_prompt.partial_format(
            num_choices=len(self.choice_descriptions),
            max_outputs=len(self.choice_descriptions),
        )

        # get choices selected by LLM
        choices_str = self._get_choice_str(self.choice_descriptions)
        output = self.llm.structured_predict(
            Answers,
            router_prompt1,
            context_list=choices_str,
            query_str=query_str
        )

        if self._verbose:
            print(f"Selected choice(s):")
            for answer in output.answers:
                print(f"Choice: {answer.choice}, Reason: {answer.reason}")

        return ChooseQueryEngineEvent(answers=output, query_str=query_str)

    @step()
    async def query_each_engine(self, ev: ChooseQueryEngineEvent) -> SynthesizeAnswersEvent:
        """Query each engine."""

        query_str = ev.query_str
        answers = ev.answers

        # query using corresponding query engine given in Answers list
        responses = []

        for answer in answers.answers:
            choice_idx = answer.choice - 1
            response = await self._query(query_str, choice_idx)
            responses.append(response)
        
        return SynthesizeAnswersEvent(responses=responses, query_str=query_str)

    @step()
    async def synthesize_response(self, ev: SynthesizeAnswersEvent) -> StopEvent:
        """Synthesizes response."""
        responses = ev.responses
        query_str = ev.query_str

        
        response_strs = [str(r) for r in responses]
        text = self.summarizer.get_response(
            query_str, 
            response_strs,
            include_metadata=True
        )
        # Extract documents from source nodes
        documents = []
        experts_map = {}  # Use a dictionary to track experts by email
        
        for response in responses:
            if hasattr(response, 'source_nodes'):
                for source_node in response.source_nodes:
                    if hasattr(source_node, 'node'):
                        node = source_node.node
                        score = source_node.score
                        print(f"Score: {score}")
                        if score < 0.2:  # Your relevance threshold
                            if hasattr(node, 'metadata'):
                                metadata = node.metadata
                                doc = {
                                    "title": metadata.get("file_name", "Untitled"),
                                    "url": metadata.get("url", ""),
                                    "page": metadata.get("page_number", "")
                                }
                                documents.append(doc)
                                
                                # Process experts and associate them with documents
                                expert_list = metadata.get("experts", [])
                                for expert in expert_list:
                                    name = expert.get("name")
                                    if name not in experts_map:
                                        # Create new expert entry with documents list
                                        experts_map[name] = {
                                            "name": name,
                                            "email": expert.get("email", ""),
                                            "image": expert.get("image", ""),
                                            "documents": [doc["title"]]
                                        }
                                    else:
                                        # Add document to existing expert if not already there
                                        if doc["title"] not in experts_map[name]["documents"]:
                                            experts_map[name]["documents"].append(doc["title"])
        
        # Convert experts map to list
        experts = list(experts_map.values())
    
        # Return formatted response
        message = {
            "text": text,
            "documents": documents,
            "experts": experts
        }
        
        return StopEvent(result=message)
