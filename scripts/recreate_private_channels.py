#!/usr/bin/env python3
"""
Ricrea canali Slack come PRIVATI con utenti default

1. Elimina canali pubblici esistenti
2. Ricrea come privati
3. Invita Giorgio e Carlo
"""
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, '/var/www/astrogen')

from agata.admin.services.slack_service import get_slack_service
from agata.auth_models import Association, SlackChannel
from agata.db import SessionLocal

load_dotenv()


def recreate_association_channels(db, association_id):
    """
    Ricrea i canali Slack per un'associazione

    Args:
        db: Database session
        association_id: ID associazione
    """
    print(f"\n{'='*60}")
    print(f"RICREAZIONE CANALI")
    print(f"{'='*60}")

    # Ottieni associazione
    association = db.query(Association).filter(Association.id == association_id).first()
    if not association:
        print(f"❌ Associazione {association_id} non trovata")
        return

    print(f"\nAssociazione: {association.name}")
    print(f"Slug: {association.slug}")

    # Elimina canali dal database (non da Slack, dovrai farlo manualmente)
    existing_channels = db.query(SlackChannel).filter(
        SlackChannel.association_id == association_id
    ).all()

    if existing_channels:
        print(f"\n1. Elimino {len(existing_channels)} canali dal database...")
        for ch in existing_channels:
            print(f"   - #{ch.channel_name} (ID: {ch.channel_id})")
            db.delete(ch)
        db.commit()
        print("   ✅ Eliminati dal database")
        print("\n   ⚠️  IMPORTANTE: Elimina manualmente i canali pubblici da Slack:")
        for ch in existing_channels:
            print(f"      https://app.slack.com/client/T0A6MPT2MPV/{ch.channel_id}")
    else:
        print("\n1. Nessun canale esistente nel database")

    # Crea nuovi canali PRIVATI
    print(f"\n2. Creo nuovi canali PRIVATI...")
    slack_service = get_slack_service()

    try:
        channels = slack_service.create_association_channels(
            db=db,
            association=association,
            user_id=None,
            user_email="system@astrogen.it"
        )

        print(f"\n✅ SUCCESSO! Creati {len(channels)} canali PRIVATI:")
        for ch in channels:
            print(f"   [PRIVATO] #{ch.channel_name}")
            print(f"             ID: {ch.channel_id}")
            print(f"             Tipo: {ch.channel_type}")
            print(f"             Link: https://app.slack.com/client/T0A6MPT2MPV/{ch.channel_id}")

        print(f"\n👥 Utenti invitati automaticamente:")
        print(f"   - Giorgio Mazzacurati (giorgio.mazzacurati@astrogen.it)")
        print(f"   - Carlo Marino (carlo.marino@astrogen.it)")

        return channels

    except Exception as e:
        print(f"\n❌ ERRORE: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def main():
    print("🚀 AGATA - Ricreazione Canali Slack PRIVATI")
    print("="*60)

    db = SessionLocal()
    try:
        # Ricrea canali per GAML e GAL Hassin
        associations = [
            (6, "Gruppo Astrofili Monti Lepini"),
            (7, "GAL Hassin")
        ]

        for assoc_id, assoc_name in associations:
            recreate_association_channels(db, assoc_id)

        print(f"\n{'='*60}")
        print("RIEPILOGO")
        print(f"{'='*60}")
        print("✅ Canali ricreati come PRIVATI")
        print("✅ Giorgio Mazzacurati e Carlo Marino invitati")
        print("\n⚠️  Ricordati di eliminare i canali pubblici vecchi da Slack:")
        print("   Settings → Manage Members → Archive Channel → Delete")

    except Exception as e:
        print(f"\n❌ ERRORE: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)

    finally:
        db.close()


if __name__ == '__main__':
    main()
