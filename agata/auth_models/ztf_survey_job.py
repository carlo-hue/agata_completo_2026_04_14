# agata/auth_models/ztf_survey_job.py
"""
ZTF Survey Job model - Tracciamento pipeline survey fotometrico ZTF

Gestisce il workflow di survey fotometrico su area di cielo con ZTF:
- Download dati fotometrici IRSA per tutte le stelle nel campo
- Calcolo indici di variabilita' (Stetson J/K, chi2, MAD, IQR)
- Identificazione candidati variabili
- Cross-match con VSX (AAVSO) e Gaia DR3
- Promozione candidati validati in agata_star_photometry
"""
from sqlalchemy import String, Integer, BigInteger, Float, Double, Boolean, ForeignKey, Text, JSON, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from agata.models import Base


class ZtfSurveyJob(Base):
    """
    Traccia una sessione di survey fotometrico ZTF su un'area di cielo.

    Workflow:
    1. Admin/superuser crea job con parametri campo (pending)
    2. Download dati da IRSA per tutte le sorgenti nell'area (downloading)
    3. Calcolo indici di variabilita' per ogni sorgente (analyzing)
    4. Cross-match con VSX e Gaia DR3 (crossmatching)
    5. Completamento (completed) o errore (failed)
    """
    __tablename__ = "agata_ztf_survey_jobs"
    __table_args__ = (
        # Filtro lista job per associazione + stato
        Index('idx_ztf_jobs_association_state', 'association_id', 'state'),
        # Filtro per creatore (admin vede solo i propri)
        Index('idx_ztf_jobs_created_by', 'created_by'),
        # Ordinamento lista (più recenti prima)
        Index('idx_ztf_jobs_created_at', 'created_at'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identificazione job
    job_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="Codice univoco job (es. ZSURVEY-2026-00001)"
    )
    target_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Nome descrittivo del campo"
    )
    association_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="Associazione proprietaria (NULL = superuser globale)"
    )

    # Parametri area di cielo
    ra_center: Mapped[float] = mapped_column(
        Double, nullable=False,
        comment="RA centro campo (gradi)"
    )
    dec_center: Mapped[float] = mapped_column(
        Double, nullable=False,
        comment="Dec centro campo (gradi)"
    )
    radius_deg: Mapped[float] = mapped_column(
        Double, nullable=False,
        comment="Raggio ricerca (gradi, max 3.0)"
    )
    ztf_filter: Mapped[str] = mapped_column(
        String(10), nullable=False, default='r',
        comment="Filtro ZTF: g, r, o i"
    )
    mag_min: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Limite magnitudine brillante (es. 12.0)"
    )
    mag_max: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Limite magnitudine debole (es. 19.5)"
    )
    min_observations: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20,
        comment="Numero minimo punti fotometrici per sorgente"
    )

    # Stato macchina workflow
    state: Mapped[str] = mapped_column(
        SQLEnum('pending', 'downloading', 'analyzing',
                'crossmatching', 'completed', 'failed', 'cancelled',
                name='ztf_survey_job_state'),
        default='pending', nullable=False,
        comment="Stato corrente del workflow"
    )
    progress_pct: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Percentuale completamento (0-100)"
    )
    current_step: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Descrizione step corrente"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Dettagli errore se state=failed"
    )

    # Statistiche risultati
    total_sources: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti ZTF totali trovate nel campo"
    )
    candidates_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti che superano le soglie di variabilita"
    )
    known_variables_found: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti matchate nel catalogo VSX"
    )
    promoted_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False,
        comment="Sorgenti promosse in agata_star_photometry"
    )

    # Dati output (JSON)
    output_data: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Metadata job: {irsa_url, query_params, promotion: {...}}"
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
        lazy="joined"
    )
    results: Mapped[list["ZtfSurveyResult"]] = relationship(
        "ZtfSurveyResult",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin"
    )

    def __repr__(self):
        return f"<ZtfSurveyJob(id={self.id}, code='{self.job_code}', state='{self.state}')>"

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

    @property
    def filtercode(self) -> str:
        """Converte filtro (g/r/i) in filtercode IRSA (zg/zr/zi)."""
        return f"z{self.ztf_filter}"

    @property
    def catalog_name(self) -> str:
        """Nome catalogo per agata_star_photometry (ZTFg/ZTFr/ZTFi)."""
        return f"ZTF{self.ztf_filter}"


class ZtfSurveyResult(Base):
    """
    Sorgente ZTF trovata nel campo survey con indici di variabilita' calcolati.

    Una riga per ogni sorgente ZTF che ha abbastanza osservazioni (>= min_observations).
    Dopo cross-match con Gaia, le sorgenti valide possono essere promosse in
    agata_star_photometry per analisi ulteriori nell'editor stelle variabili.
    """
    __tablename__ = "agata_ztf_survey_results"
    __table_args__ = (
        # Join principale: risultati per job
        Index('idx_ztf_results_job_id', 'job_id'),
        # Lookup per Gaia source ID (cross-match, promozione)
        Index('idx_ztf_results_gaia_source_id', 'gaia_source_id'),
        # Filtro candidati da mostrare nella pagina dettaglio
        Index('idx_ztf_results_flags', 'job_id', 'is_candidate', 'is_valid'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Job padre
    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agata_ztf_survey_jobs.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID job padre"
    )

    # Identificazione sorgente ZTF
    ztf_object_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="ZTF object ID (colonna oid da IRSA)"
    )
    ra: Mapped[float] = mapped_column(
        Double, nullable=False,
        comment="Right Ascension (gradi) - media pesata da ZTF"
    )
    decl: Mapped[float] = mapped_column(
        Double, nullable=False,
        comment="Declination (gradi) - media pesata da ZTF"
    )

    # Riepilogo fotometrico
    n_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Osservazioni ZTF totali prima del filtro qualita"
    )
    n_points_used: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="Punti usati dopo catflags==0 e filtri"
    )
    mean_mag: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Magnitudine media pesata"
    )
    std_dev: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Deviazione standard (RMS scatter)"
    )
    mag_err_median: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Errore fotometrico mediano per punto"
    )

    # Indici di variabilita'
    stetson_j: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Stetson J index (variabilita correlata)"
    )
    stetson_k: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Stetson K index (curtosi residui)"
    )
    chi_squared: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Chi-quadrato ridotto vs magnitudine media pesata"
    )
    mad: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Median Absolute Deviation"
    )
    iqr: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        comment="Interquartile Range"
    )

    # Flag candidato e classificazione
    is_candidate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se stetson_j o chi2 superano le soglie"
    )
    is_known_variable: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se matchato nel catalogo VSX (AAVSO)"
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
        comment="False se match Gaia ambiguo o assente"
    )
    is_ambiguous: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se match Gaia usa fallback 100 arcsec"
    )
    is_rejected: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se l'utente ha esplicitamente rifiutato questa stella"
    )
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True se un OID ZTF con piu osservazioni mappa allo stesso gaia_source_id"
    )

    # Risultati cross-match
    gaia_source_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
        comment="Gaia DR3 source_id da cross-match"
    )
    vsx_match: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="Match VSX: {oid, name, type}"
    )
    catalog_matches: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="CSV: Gaia,AAVSO"
    )
    variable_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="Tipo variabile dal campo VSX Type"
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
    job: Mapped["ZtfSurveyJob"] = relationship(
        "ZtfSurveyJob",
        back_populates="results",
        foreign_keys=[job_id]
    )
    project: Mapped["Project"] = relationship(
        "Project",
        foreign_keys=[project_id],
        lazy="joined"
    )

    def __repr__(self):
        return (f"<ZtfSurveyResult(id={self.id}, job_id={self.job_id}, "
                f"ra={self.ra:.4f}, is_candidate={self.is_candidate})>")

    @property
    def is_promotable(self) -> bool:
        """True se la sorgente puo' essere promossa (ha Gaia ID valido e non e' duplicata)."""
        return self.is_valid and self.gaia_source_id is not None and not self.is_duplicate
