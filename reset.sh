read -p "Are you sure? " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo deleting all data
    find data -type f -delete
    find logs -type f -delete
else
    echo cancelled
fi
