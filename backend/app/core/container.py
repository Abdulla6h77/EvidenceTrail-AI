from dataclasses import dataclass

from app.core.config import Settings
from app.integrations.hmem import HMEMStore, ReferenceHMEMStore
from app.integrations.nemotron import NemotronAdapter
from app.integrations.sql import ReadOnlySQLExecutor
from app.integrations.zetaris import ZetarisAdapter
from app.services.investigation import InvestigationWorkflow
from app.storage.database import Database
from app.storage.investigations import InvestigationStore


@dataclass
class AppServices:
    settings: Settings
    database: Database
    investigations: InvestigationStore
    hmem: HMEMStore | ReferenceHMEMStore
    sql: ReadOnlySQLExecutor
    zetaris: ZetarisAdapter
    nemotron: NemotronAdapter
    workflow: InvestigationWorkflow


def build_services(settings: Settings) -> AppServices:
    database = Database(settings.database_file)
    database.ensure_seeded()
    investigations = InvestigationStore(settings.database_file.with_suffix(".investigations.json"))
    hmem = (
        ReferenceHMEMStore(settings.database_file.with_suffix(".meterless-hmem"), settings.meterless_hmem_node_binary)
        if settings.meterless_hmem_enabled
        else HMEMStore(settings.database_file.with_suffix(".hmem.json"))
    )
    sql = ReadOnlySQLExecutor(database, settings)
    zetaris = ZetarisAdapter(settings)
    nemotron = NemotronAdapter(settings)
    workflow = InvestigationWorkflow(settings, sql, hmem, investigations, zetaris=zetaris, nemotron=nemotron)
    return AppServices(
        settings=settings,
        database=database,
        investigations=investigations,
        hmem=hmem,
        sql=sql,
        zetaris=zetaris,
        nemotron=nemotron,
        workflow=workflow,
    )
