from dotenv import load_dotenv
from pipeline.config import Config
from pipeline.agents.orchestrator import OrchestratorAgent

load_dotenv()

if __name__ == "__main__":
    config = Config()
    orchestrator = OrchestratorAgent(config)
    orchestrator.run()
