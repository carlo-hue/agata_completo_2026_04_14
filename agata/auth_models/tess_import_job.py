# agata/auth_models/tess_import_job.py
"""
TESS Bulk Import Job model - Tracciamento pipeline import massivo TESS QLP da MAST

Gestisce il workflow di import batch di curve di luce TESS QLP da curl script MAST:
- Parsing del curl script per estrarre TIC ID, settore, URL FITS
- Download FITS da MAST per N stelle selezionate
- Calcolo indici di variabilita' (Stetson J/K, chi2, MAD, IQR)
- Identificazione candidati variabili
- Cross-match con VSX (AAVSO), ATLAS e catalogo variabilita' Gaia (pattern VAST)
- Cross-match TIC->Gaia DR3 per identificazione univoca
- Promozione candidati in agata_star_photometry
"""
from sqlalchemy import String, Integer, BigInteger, Float, Double, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from agata.models import Base


class TessImportJob(Base):
    """
    Traccia una sessione di import batch di curve di luce TESS QLP da curl script MAST.

    Workflow:
    1. Admin carica curl script MAST + seleziona N stelle (pending)
    2. Download FITS da MAST + ingest QLP + calcolo indici variabilita' (downloading)
    3. Identificazione candidati (analyzing)
    4. Cross-match VSX + ATLAS + Gaia flags + TIC->Gaia DR3 (crossmatching)
    5. Completamento (completed) o errore (failed)
    """
    __tablename__ = "agata_tess_import_jobs"
    __table_args__ = (
        Index('idx_tess_import_jobs_assoc_state', 'association_id', 'state'),
        Index('idx_tess_import_jobs_created_by', 'created_by'),
        Index('idx_tess_import_jobs_created_at', 'created_at'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificazione job
    job_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="Codice univoco job (es. TESS_IMPORT-S84-00001, sequenziale per settore)"
    )
    job_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Nome descrittivo del job"
    )
    association_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Associazione proprietaria (NULL = superuser globale)"
    )

    # Metadati curl script (legacy path: multipart upload) o FK to script library
    curl_script_filename: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Nome originale del file curl script caricato (legacy path, NULL for script library)"
    )
    curl_script_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agata_tess_curl_scripts.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK to TessCurlScript (script library path, NULL for legacy jobs)"
    )
    script_offset: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Zero-based offset into agata_tess_curl_entries (for script library batching)"
    )
    total_files_in_script: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Numero totale di file FITS nel curl script"
    )
    files_selected: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="N file selezionati per elaborazione"
    )
    selection_strategy: Mapped[str] = mapped_column(
        SQLEnum('first_n', 'random_n', name='tess_import_selection_strategy'),
        default='first_n', nullable=False,
        comment="Strategia selezione file: first_n o random_n"
    )

    # Impostazioni pipeline
    mast_download_timeout: Mapped[int] = mapped_column(
        Integer, default=120, nullable=False,
        comment="Timeout download FITS da MAST (secondi)"
    )
    min_observations: Mapped[int] = mapped_column(
        Integer, default=20, nullable=False,
        comment="Minimo punti fotometrici per curva valida"
    )
    stetson_j_threshold: Mapped[float] = mapped_column(
        Float, default=0.5, nullable=False,
        comment="Soglia Stetson J per is_candidate=True"
    )
    chi2_threshold: Mapped[float] = mapped_column(
        Float, default=3.0, nullable=False,
        comment="Soglia chi-quadrato ridotto per is_candidate=True"
    )

    # Stato macchina workflow
    state: Mapped[str] = mapped_column(
        SQLEnum('pending', 'downloading', 'analyzing',
                'crossmatching', 'completed', 'failed', 'cancelled',
                name='tess_import_job_state'),
        default='pending', nullable=False,
        comment="Stato corrente del workflow"
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Percentuale completamento (0-100)"
    )
    current_step: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Descrizione step corrente"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Dettagli errore se state=failed"
    )

    # Statistiche risultati
    total_processed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="File FITS elaborati con successo"
    )
    total_failed_downloads: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="File FITS non scaricabili (timeout, 404, etc.)"
    )
    candidates_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti che superano le soglie di variabilita'"
    )
    known_variables_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti matchate in VSX o catalogo Gaia variabili"
    )
    promoted_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti promosse in agata_star_photometry"
    )

    # Dati output JSON (lista file selezionati + metadati promozione)
    output_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Metadata: {selected_files: [...], promotion: {...}}"
    )

    # Proprietario e audit
    created_by: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agata_users.id", ondelete="CASCADE"),
        nullable=False,
        comment="UUID utente che ha creato il job"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False,
        comment="Data creazione job"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Data inizio elaborazione"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="Data completamento job"
    )

    # Relationships
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="select"
    )
    curl_script: Mapped["TessCurlScript"] = relationship(
        "TessCurlScript",
        foreign_keys=[curl_script_id],
        lazy="select",
        back_populates="jobs"
    )
    results: Mapped[list["TessImportResult"]] = relationship(
        "TessImportResult",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self):
        return f"<TessImportJob(id={self.id}, code='{self.job_code}', state='{self.state}')>"

    @property
    def is_running(self) -> bool:
        """True se il job e' in elaborazione."""
        return self.state in ['downloading', 'analyzing', 'crossmatching']

    @property
    def is_failed(self) -> bool:
        """True se il job e' fallito."""
        return self.state == 'failed'

    @property
    def duration_seconds(self) -> float | None:
        """Durata job in secondi."""
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()


class TessImportResult(Base):
    """
    Sorgente TESS da un singolo file FITS QLP con indici di variabilita' calcolati.

    Una riga per ogni file FITS elaborato (con successo o meno).
    Dopo cross-match con Gaia DR3, le sorgenti valide possono essere promosse in
    agata_star_photometry. La curva di luce completa e' stored in lc_full_json
    per evitare re-download da MAST al momento della promozione.
    """
    __tablename__ = "agata_tess_import_results"
    __table_args__ = (
        Index('idx_tess_results_job_id', 'job_id'),
        Index('idx_tess_results_gaia_source_id', 'gaia_source_id'),
        Index('idx_tess_results_tic_id', 'tic_id'),
        Index('idx_tess_results_flags', 'job_id', 'is_candidate', 'is_valid'),
        Index('idx_tess_results_download', 'job_id', 'download_failed'),
        UniqueConstraint('job_id', 'tic_id', 'sector', name='uq_tess_results_job_tic_sector'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Job padre
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agata_tess_import_jobs.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID job padre"
    )

    # Identificazione sorgente TESS
    tic_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="TESS Input Catalog ID (estratto dal filename)"
    )
    sector: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Settore TESS (estratto dal filename)"
    )
    fits_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True,
        comment="URL MAST originale dal curl script"
    )
    fits_filename: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Path relativo dal curl script (output field)"
    )

    # Coordinate (da FITS PRIMARY header RA_OBJ / DEC_OBJ)
    ra: Mapped[float | None] = mapped_column(
        Double, nullable=True,
        comment="Right Ascension (gradi) da header FITS RA_OBJ"
    )
    decl: Mapped[float | None] = mapped_column(
        Double, nullable=True,
        comment="Declination (gradi) da header FITS DEC_OBJ"
    )

    # Riepilogo fotometrico
    tess_mag: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="TESSMAG dal header FITS PRIMARY"
    )
    curve_used: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="Curva usata: corrected (KSPSAP) o raw (SAP)"
    )
    n_points: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Punti totali nel FITS"
    )
    n_points_used: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Punti dopo pulizia NaN/qualita'"
    )
    mean_mag: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Magnitudine media"
    )
    std_dev: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Deviazione standard (RMS scatter)"
    )
    mag_err_median: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Errore fotometrico mediano"
    )

    # Indici di variabilita' (stessi 8 del pipeline ZTF)
    stetson_j: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Stetson J index"
    )
    stetson_k: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Stetson K index"
    )
    chi_squared: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Chi-quadrato ridotto"
    )
    mad: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Median Absolute Deviation"
    )
    iqr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Interquartile Range"
    )

    # Flag
    is_candidate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se stetson_j o chi2 superano le soglie"
    )
    is_known_variable: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se matchato in VSX o catalogo Gaia variabili (non solo ATLAS)"
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="False se match Gaia assente o ambiguo"
    )
    is_ambiguous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se match Gaia usa fallback RA/Dec invece di TIC"
    )
    download_failed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se il download MAST e' fallito per questa sorgente"
    )
    download_error: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="Messaggio errore download se download_failed=True"
    )
    is_rejected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se l'utente ha manualmente rifiutato questa stella (non sara' promossa)"
    )

    # Risultati cross-match (stile VAST: tre cataloghi)
    gaia_source_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="Gaia DR3 source_id"
    )
    vsx_match: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Match VSX: {oid, name, type}"
    )
    atlas_match: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Match ATLAS: {atoid, class} da J/AJ/156/241"
    )
    gaia_variability_flags: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Nome flag variabilita' Gaia (es. VRRLyr, VCep) se presente"
    )
    catalog_matches: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="CSV: Gaia,AAVSO,Atlas"
    )
    variable_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Tipo variabile da VSX o flag Gaia"
    )

    # Storage curva di luce
    lc_preview_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="LC downsampled: {hjd:[...], mag:[...]} max 200 punti per sparkline UI"
    )
    lc_full_json: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="LC completa: {hjd:[...], mag:[...], mag_err:[...]} per promozione senza re-download"
    )

    # Link a progetto (impostato dopo promozione)
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("agata_projects.id", ondelete="SET NULL"),
        nullable=True,
        comment="agata_projects.id se promosso a progetto"
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False,
        comment="Data creazione risultato"
    )

    # Relationships
    job: Mapped["TessImportJob"] = relationship(
        "TessImportJob",
        back_populates="results",
        foreign_keys=[job_id]
    )
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="joined"
    )

    def __repr__(self):
        return (f"<TessImportResult(id={self.id}, job_id={self.job_id}, "
                f"tic_id={self.tic_id}, sector={self.sector}, "
                f"is_candidate={self.is_candidate})>")

    @property
    def is_promotable(self) -> bool:
        """True se la sorgente puo' essere promossa."""
        return (
            self.is_valid
            and self.gaia_source_id is not None
            and not self.download_failed
            and self.lc_full_json is not None
        )
