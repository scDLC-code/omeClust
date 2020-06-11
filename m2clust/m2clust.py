#!/usr/bin/env python

"""
Multi-resolution clustering approach to find clusters with different diameter 

"""
import argparse
import os
import sys
import logging
import pandas as pd
from numpy import array
from scipy.cluster.hierarchy import to_tree, linkage
from scipy.spatial.distance import pdist, squareform

# name global logging instance
logger = logging.getLogger(__name__)

VERSION = "1.1.3"
try:
    from . import utilities, config, dataprocess
except ImportError:
    sys.exit("CRITICAL ERROR: Unable to find the utilities module." +
             " Please check your m2clust install.")
from . import distance, viz

def main_run(distance_matrix=None,
             number_of_estimated_clusters=None,
             linkage_method='single',
             output_dir=None,
             do_plot=True,
             resolution='low'):
    bTree = True
    if do_plot:
        Z = viz.dendrogram_plot(data_table=None, D=distance_matrix, xlabels_order=[], xlabels=distance_matrix.index,
                                filename=output_dir + "/dendrogram", colLable=False, rowLabel=False,
                                linkage_method=linkage_method)
    else:
        Z = linkage(squareform(distance_matrix), method=linkage_method)

    hclust_tree = to_tree(Z)
    # clusters = cutree_to_get_below_threshold_number_of_features (hclust_tree, t = estimated_num_clust)
    if number_of_estimated_clusters == None:
        number_of_estimated_clusters, _ = utilities.predict_best_number_of_clusters(hclust_tree, distance_matrix)
    clusters = utilities.get_homogenous_clusters_silhouette(hclust_tree, array(distance_matrix),
                                                            number_of_estimated_clusters=number_of_estimated_clusters,
                                                            resolution=resolution)
    # print [cluster.pre_order(lambda x: x.id) for cluster in clusters]
    # print(len(clusters))
    return clusters


def check_requirements():
    """
    Check requirements (file format, dependencies, permissions)
    """
    # check the third party softwares for plotting the results
    try:
        import pandas as pd
    except ImportError:
        sys.exit("--- Please check your installation for pandas library")
    # Check that the output directory is writeable
    output_dir = os.path.abspath(config.output_dir)
    if not os.path.isdir(output_dir):
        try:
            print("Creating output directory: " + output_dir)
            os.mkdir(output_dir)
        except EnvironmentError:
            sys.exit("CRITICAL ERROR: Unable to create output directory.")


def parse_arguments(args):
    """ 
    Parse the arguments from the user
    """

    parser = argparse.ArgumentParser(
        description="Multi-resolution clustering using hierarchical clustering and Silhouette score.\n",
        formatter_class=argparse.RawTextHelpFormatter,
        prog="m2clust")
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + config.version)
    parser.add_argument(
        "-i", "--input",
        help="the input file D*N, Rows: D features and columns: N samples OR \n" +
             "a distance matrix file D*D (rows and columns should be the same and in the same order) \n ",
        required=False)
    parser.add_argument(
        "-o", "--output",
        help="the output directory\n",
        required=True)
    parser.add_argument(
        "-m", "--similarity",
        default='spearman',
        help="similarity measurement {default spearman, options: spearman, nmi, ami, dmic, mic, pearson, dcor}")
    parser.add_argument(
        "--metadata",
        default=None,
        help="Rows are features and each column is a metadata")
    parser.add_argument(
        "-n", "--estimated_number_of_clusters",
        type=int,
        default=2,
        help="estimated number of clusters")
    parser.add_argument(
        "--size-to-plot",
        type=int,
        dest='size_to_plot',
        default=None,
        help="Minimum size of cluster to be plotted")
    parser.add_argument(
        "-c", "--linkage_method",
        default='single',
        help="linkage clustering method method {default = single, options average, complete\n")
    parser.add_argument(
        "--plot",
        help="dendrogram plus heatmap\n",
        action="store_true",
        default=False)
    parser.add_argument(
        "--resolution",
        default='low',
        help="Resolution c .\
         Low resolution is good when clusters are well separated clusters.",
        choices=['high', 'medium', 'low'])
    parser.add_argument(
        "-v", "--verbose",
        help="additional output is printed\n",
        action="store_true",
        default=False)
    return parser.parse_args()


def m2clust(data, metadata, resolution=config.resolution,
            output_dir=config.output_dir,
            estimated_number_of_clusters=config.estimated_number_of_clusters,
            linkage_method=config.linkage_method, plot=config.plot, size_to_plot=None):
    # read  input files
    data = pd.read_table(data, index_col=0, header=0)
    # print(data.shape)
    # print(data.index)
    # print(data.columns)
    if metadata is not None:
        metadata = pd.read_table(metadata, index_col=0, header=0)
        # print(data.index)
        # print(metadata.index)
        ind = metadata.index.intersection(data.index)
        # print(len(ind), data.shape[1])
        if len(ind) != data.shape[0]:
            print("the data and metadata have different number of rows and number of common rows is: ", len(ind))
            print("The number of missing metadata are: ", data.shape[0] - len(ind))
            # print("Metadata will not be used!!! ")
            # metadata = None
            # else:
        metadata = metadata.loc[ind, :]
        data = data.loc[ind, ind]

    config.output_dir = output_dir
    check_requirements()
    data_flag = True

    if all(a == b for (a, b) in zip(data.columns, data.index)):
        df_distance = data
        data_flag = False
    else:
        df_distance = pd.DataFrame(squareform(pdist(data, metric=distance.pDistance)), index=data.index,
                                   columns=data.index)
    df_distance = df_distance[df_distance.values.sum(axis=1) != 0]
    df_distance = df_distance[df_distance.values.sum(axis=0) != 0]
    df_distance.to_csv(output_dir + '/adist.txt', sep='\t')
    # df_distance = stats.scale_data(df_distance, scale = 'log')

    # viz.tsne_ord(df_distance, target_names = data.columns)
    clusters = main_run(distance_matrix=df_distance,
                        number_of_estimated_clusters=estimated_number_of_clusters,
                        linkage_method=linkage_method,
                        output_dir=output_dir, do_plot=plot, resolution=resolution)
    m2clust_enrichment_scores, sorted_keys = None, None
    shapeby = None
    if metadata is not None:
        m2clust_enrichment_scores, sorted_keys = utilities.m2clust_enrichment_score(clusters, metadata,
                                                                                    df_distance.shape[0])
        if len(sorted_keys) > 2:
            shapeby = sorted_keys[2]
            print(shapeby, " is the most influential metadata in clusters")
    else:
        m2clust_enrichment_scores, sorted_keys = utilities.m2clust_enrichment_score(clusters, metadata,
                                                                                    df_distance.shape[0])
    # print m2clust_enrichment_scores, sorted_keys
    dataprocess.write_output(clusters, output_dir, df_distance, m2clust_enrichment_scores, sorted_keys)
    if size_to_plot is None:
        size_to_plot = config.size_to_plot
    viz.mds_ord(df_distance, target_names=dataprocess.cluster2dict(clusters), \
                size_tobe_colered=size_to_plot, metadata=metadata, shapeby=shapeby)
    viz.pcoa_ord(df_distance, target_names=dataprocess.cluster2dict(clusters), \
                 size_tobe_colered=size_to_plot, metadata=metadata, shapeby=shapeby)
    viz.tsne_ord(df_distance, target_names=dataprocess.cluster2dict(clusters), \
                 size_tobe_colered=size_to_plot, metadata=metadata, shapeby=shapeby)
    viz.pca_ord(data, target_names=dataprocess.cluster2dict(clusters), \
                 size_tobe_colered=size_to_plot, metadata=metadata, shapeby=shapeby)


def update_configuration(args):
    # configure the logger
    logging.basicConfig(filename=args.output + '/m2clust_log.txt',
                        format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
                        level=getattr(logging, "INFO"), filemode='w', datefmt='%m/%d/%Y %I:%M:%S %p')

    # write the version of the software to the log
    logger.info("Running m2clust version:\t" + VERSION)

    # write the version of the software to the log
    logger.info("resolution level:\t" + args.resolution)


def main():
    # Parse arguments from command line
    args = parse_arguments(sys.argv)
    config.similarity = args.similarity
    config.output_dir = args.output + "/"

    dataprocess.create_output(config.output_dir)
    config.input = args.input
    config.output = args.output
    config.resolution = args.resolution
    config.out_dir = args.output
    config.estimated_number_of_clusters = args.estimated_number_of_clusters
    config.linkage_method = args.linkage_method
    config.plot = args.plot
    config.size_to_plot = args.size_to_plot
    config.estimated_number_of_clusters = args.estimated_number_of_clusters,
    config.linkage_method = args.linkage_method
    config.plot = config.plot
    config.size_to_plot = config.size_to_plot
    m2clust(data=args.input, metadata=args.metadata,
            resolution=args.resolution, output_dir=args.output,
            linkage_method=args.linkage_method,
            plot=args.plot,
            estimated_number_of_clusters=args.estimated_number_of_clusters,
            size_to_plot=args.size_to_plot)
    update_configuration(config)


if __name__ == "__main__":
    main()
