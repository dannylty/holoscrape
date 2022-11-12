read -p "Are you sure? " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo deleting all data
    find /mnt/thumb/hololive/data -type f -delete
    find /mnt/thumb/hololive/logs -type f -delete
else
    echo cancelled
fi
