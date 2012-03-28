from django.core.management.base import LabelCommand, CommandError
from couchexport.models import SavedExportSchema
from optparse import make_option

OLD_ROOT_INDEX = "#.#"
NEW_ROOT_INDEX = "#"

class Command(LabelCommand):
    help = "Migrates over custom exports from the old format to the new format."
    args = ""
    label = ""
    
    option_list = LabelCommand.option_list + \
        (make_option('--dryrun', action='store_true', dest='dryrun', default=False,
            help="Don't do the actual migration, just print the output"),)

    
    def handle(self, *args, **options):
        if len(args) != 0: raise CommandError("This command doesn't expect arguments!")
            
        for export in SavedExportSchema.view("couchexport/saved_export_schemas", include_docs=True):
            print "migrating %s" % export
            if not hasattr(export, 'type'):
                export.type = 'form'
                if not options['dryrun']:
                    export.save()
        print "Done!" 
                
